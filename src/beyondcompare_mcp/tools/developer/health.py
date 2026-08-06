"""
Repository Health Checker and Cleanup Tools.

Tools for monitoring repository health, detecting issues, and performing
automated cleanup of build artifacts and temporary files.
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RepositoryHealthChecker:
    """Repository health monitoring and cleanup tools."""

    # Default cleanup targets
    DEFAULT_CLEANUP_TARGETS = [
        "node_modules",
        "__pycache__",
        "target",  # Rust build directory
        "dist",
        "build",
        "*.log",
        "*.tmp",
        ".pytest_cache",
        "coverage",
        ".nyc_output",  # NYC coverage
        ".coverage",  # Python coverage
        "*.pyc",
        "*.pyo",
        ".DS_Store",
        "Thumbs.db",
        "*.swp",
        "*.swo",
        ".vscode/settings.json",  # User-specific VS Code settings
    ]

    # Health check types
    HEALTH_CHECKS = {
        "git_status": "Check for uncommitted changes and repository status",
        "large_files": "Identify files larger than specified threshold",
        "security_issues": "Scan for potential security issues",
        "dependency_outdated": "Check for outdated dependencies",
        "disk_usage": "Analyze disk usage and cleanup opportunities",
        "code_quality": "Basic code quality checks",
        "documentation": "Check for essential documentation files",
    }

    def __init__(self, bc_path: Path | None = None):
        """Initialize the health checker.

        Args:
            bc_path: Path to Beyond Compare executable
        """
        self.bc_path = bc_path

    def scan_repository_health(
        self, repos_path: str, checks: list[str] | None = None, report_path: str | None = None, fix_issues: bool = False
    ) -> dict[str, Any]:
        """Scan repository health and identify issues.

        Args:
            repos_path: Path to repositories directory
            checks: List of checks to perform
            report_path: Optional path to save report
            fix_issues: Attempt to fix detected issues

        Returns:
            Health scan results
        """
        start_time = time.time()

        try:
            repos_dir = Path(repos_path)
            if not repos_dir.exists():
                raise FileNotFoundError(f"Repository path does not exist: {repos_dir}")

            # Use all checks if none specified
            if checks is None:
                checks = list(self.HEALTH_CHECKS.keys())

            # Find repositories
            repositories = self._find_repositories(repos_dir)
            logger.info(f"Scanning health of {len(repositories)} repositories")

            # Perform health checks
            health_results = []
            total_issues = 0
            fixed_issues = 0

            for repo_path in repositories:
                repo_health = self._check_repository_health(repo_path, checks, fix_issues)
                health_results.append(repo_health)
                total_issues += len(repo_health.get("issues", []))
                fixed_issues += len(repo_health.get("fixes_applied", []))

            # Generate summary
            summary = {
                "success": True,
                "operation": "scan_repo_health",
                "execution_time_seconds": round(time.time() - start_time, 2),
                "summary": {
                    "repositories_scanned": len(repositories),
                    "total_issues_found": total_issues,
                    "issues_fixed": fixed_issues if fix_issues else 0,
                    "checks_performed": checks,
                    "fix_mode": fix_issues,
                },
                "repositories": health_results,
                "recommendations": self._generate_health_recommendations(health_results),
            }

            # Generate report if requested
            if report_path:
                self._generate_health_report(summary, report_path)
                summary["report_path"] = report_path

            return summary

        except Exception as e:
            logger.error(f"Repository health scan failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def cleanup_development_artifacts(
        self, repos_path: str, targets: list[str] | None = None, size_threshold_mb: float = 100, dry_run: bool = True
    ) -> dict[str, Any]:
        """Clean up build artifacts and temporary files.

        Args:
            repos_path: Path to repositories directory
            targets: List of patterns to clean
            size_threshold_mb: Only clean if savings exceed threshold
            dry_run: Preview without executing

        Returns:
            Cleanup summary
        """
        start_time = time.time()

        try:
            repos_dir = Path(repos_path)
            if not repos_dir.exists():
                raise FileNotFoundError(f"Repository path does not exist: {repos_dir}")

            # Use default targets if none specified
            if targets is None:
                targets = self.DEFAULT_CLEANUP_TARGETS.copy()

            # Find repositories
            repositories = self._find_repositories(repos_dir)
            logger.info(f"Analyzing cleanup opportunities in {len(repositories)} repositories")

            # Analyze cleanup opportunities
            cleanup_results = []
            total_size_mb = 0
            total_files = 0

            for repo_path in repositories:
                repo_cleanup = self._analyze_repository_cleanup(repo_path, targets, dry_run)
                cleanup_results.append(repo_cleanup)
                total_size_mb += repo_cleanup.get("potential_savings_mb", 0)
                total_files += repo_cleanup.get("files_to_remove", 0)

            # Check if cleanup meets threshold
            meets_threshold = total_size_mb >= size_threshold_mb

            # Execute cleanup if not dry run and meets threshold
            if not dry_run and meets_threshold:
                for result in cleanup_results:
                    if result.get("cleanup_targets"):
                        self._execute_cleanup(result["repository_path"], result["cleanup_targets"])
                        result["cleanup_executed"] = True

            # Generate summary
            summary = {
                "success": True,
                "operation": "cleanup_dev_artifacts",
                "dry_run": dry_run,
                "execution_time_seconds": round(time.time() - start_time, 2),
                "summary": {
                    "repositories_analyzed": len(repositories),
                    "total_potential_savings_mb": round(total_size_mb, 2),
                    "total_files_to_remove": total_files,
                    "meets_threshold": meets_threshold,
                    "threshold_mb": size_threshold_mb,
                    "cleanup_executed": not dry_run and meets_threshold,
                },
                "cleanup_targets": targets,
                "repositories": cleanup_results,
            }

            return summary

        except Exception as e:
            logger.error(f"Development artifacts cleanup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def _find_repositories(self, repos_dir: Path) -> list[Path]:
        """Find all repositories in directory.

        Args:
            repos_dir: Directory to search

        Returns:
            List of repository paths
        """
        repositories = []

        try:
            for item in repos_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    # Check for project indicators
                    indicators = [".git", "package.json", "requirements.txt", "Cargo.toml", "pom.xml"]
                    if any((item / indicator).exists() for indicator in indicators):
                        repositories.append(item)
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {repos_dir}: {e}")

        return sorted(repositories)

    def _check_repository_health(self, repo_path: Path, checks: list[str], fix_issues: bool) -> dict[str, Any]:
        """Check health of a single repository.

        Args:
            repo_path: Repository to check
            checks: Health checks to perform
            fix_issues: Whether to attempt fixes

        Returns:
            Repository health results
        """
        health_result = {
            "repository": repo_path.name,
            "repository_path": str(repo_path),
            "issues": [],
            "warnings": [],
            "recommendations": [],
            "fixes_applied": [] if fix_issues else None,
        }

        try:
            # Git status check
            if "git_status" in checks and (repo_path / ".git").exists():
                self._check_git_status(repo_path, health_result, fix_issues)

            # Large files check
            if "large_files" in checks:
                self._check_large_files(repo_path, health_result, fix_issues)

            # Security issues check
            if "security_issues" in checks:
                self._check_security_issues(repo_path, health_result, fix_issues)

            # Disk usage check
            if "disk_usage" in checks:
                self._check_disk_usage(repo_path, health_result, fix_issues)

            # Documentation check
            if "documentation" in checks:
                self._check_documentation(repo_path, health_result, fix_issues)

            # Code quality check
            if "code_quality" in checks:
                self._check_code_quality(repo_path, health_result, fix_issues)

        except Exception as e:
            logger.error(f"Health check failed for {repo_path.name}: {e}")
            health_result["error"] = str(e)

        return health_result

    def _check_git_status(self, repo_path: Path, result: dict[str, Any], fix_issues: bool) -> None:
        """Check Git repository status.

        Args:
            repo_path: Repository path
            result: Results dictionary to update
            fix_issues: Whether to attempt fixes
        """
        try:
            import subprocess

            # Check for uncommitted changes
            git_result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True, timeout=10
            )

            if git_result.returncode == 0 and git_result.stdout.strip():
                uncommitted_files = git_result.stdout.strip().split("\n")
                result["warnings"].append(f"Found {len(uncommitted_files)} uncommitted changes")
                result["recommendations"].append("Review and commit pending changes")

            # Check for untracked files
            git_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if git_result.returncode == 0 and git_result.stdout.strip():
                untracked_files = git_result.stdout.strip().split("\n")
                if len(untracked_files) > 10:  # Many untracked files might indicate missing .gitignore
                    result["warnings"].append(f"Found {len(untracked_files)} untracked files")
                    result["recommendations"].append("Consider updating .gitignore")

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            result["warnings"].append("Could not check Git status")

    def _check_large_files(self, repo_path: Path, result: dict[str, Any], fix_issues: bool) -> None:
        """Check for large files in repository.

        Args:
            repo_path: Repository path
            result: Results dictionary to update
            fix_issues: Whether to attempt fixes
        """
        large_files = []
        size_threshold = 100 * 1024 * 1024  # 100MB

        try:
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    try:
                        size = file_path.stat().st_size
                        if size > size_threshold:
                            size_mb = size / 1024 / 1024
                            relative_path = str(file_path.relative_to(repo_path))
                            large_files.append({"path": relative_path, "size_mb": round(size_mb, 1)})
                    except (OSError, PermissionError):
                        pass

            if large_files:
                result["issues"].append(f"Found {len(large_files)} files larger than 100MB")
                result["recommendations"].append("Consider using Git LFS for large files")
                result["large_files"] = large_files

        except Exception as e:
            result["warnings"].append(f"Could not check file sizes: {e}")

    def _check_security_issues(self, repo_path: Path, result: dict[str, Any], fix_issues: bool) -> None:
        """Check for potential security issues.

        Args:
            repo_path: Repository path
            result: Results dictionary to update
            fix_issues: Whether to attempt fixes
        """
        security_patterns = [
            ".env",
            "*.key",
            "*.pem",
            "id_rsa",
            "id_dsa",
            "*.p12",
            "*.pfx",
            "config.json",  # Might contain secrets
        ]

        potential_secrets = []

        try:
            for pattern in security_patterns:
                for file_path in repo_path.rglob(pattern):
                    if file_path.is_file():
                        relative_path = str(file_path.relative_to(repo_path))
                        potential_secrets.append(relative_path)

            if potential_secrets:
                result["warnings"].append(f"Found {len(potential_secrets)} files that might contain secrets")
                result["recommendations"].append("Review files for sensitive information and update .gitignore")
                result["potential_secrets"] = potential_secrets

        except Exception as e:
            result["warnings"].append(f"Could not check for security issues: {e}")

    def _check_disk_usage(self, repo_path: Path, result: dict[str, Any], fix_issues: bool) -> None:
        """Check disk usage and cleanup opportunities.

        Args:
            repo_path: Repository path
            result: Results dictionary to update
            fix_issues: Whether to attempt fixes
        """
        try:
            cleanup_opportunities = []
            total_cleanup_size = 0

            # Check for common build artifacts
            for target in self.DEFAULT_CLEANUP_TARGETS:
                if "*" in target:
                    # Handle glob patterns
                    matches = list(repo_path.rglob(target))
                else:
                    # Handle directory names
                    matches = list(repo_path.rglob(target))

                if matches:
                    target_size = 0
                    for match in matches:
                        if match.is_file():
                            try:
                                target_size += match.stat().st_size
                            except (OSError, PermissionError):
                                pass
                        elif match.is_dir():
                            target_size += self._calculate_directory_size(match)

                    if target_size > 1024 * 1024:  # >1MB
                        size_mb = target_size / 1024 / 1024
                        cleanup_opportunities.append(
                            {"target": target, "matches": len(matches), "size_mb": round(size_mb, 2)}
                        )
                        total_cleanup_size += size_mb

            if cleanup_opportunities:
                result["cleanup_opportunities"] = cleanup_opportunities
                result["potential_cleanup_mb"] = round(total_cleanup_size, 2)

                if total_cleanup_size > 100:  # >100MB
                    result["recommendations"].append(
                        f"Consider cleanup - potential savings: {round(total_cleanup_size, 1)}MB"
                    )

        except Exception as e:
            result["warnings"].append(f"Could not analyze disk usage: {e}")

    def _check_documentation(self, repo_path: Path, result: dict[str, Any], fix_issues: bool) -> None:
        """Check for essential documentation.

        Args:
            repo_path: Repository path
            result: Results dictionary to update
            fix_issues: Whether to attempt fixes
        """
        essential_docs = {
            "README": ["README.md", "README.txt", "README.rst", "README"],
            "LICENSE": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
            "CHANGELOG": ["CHANGELOG.md", "CHANGELOG.txt", "HISTORY.md"],
            "CONTRIBUTING": ["CONTRIBUTING.md", "CONTRIBUTING.txt"],
        }

        missing_docs = []

        try:
            for doc_type, filenames in essential_docs.items():
                found = False
                for filename in filenames:
                    if (repo_path / filename).exists():
                        found = True
                        break

                if not found:
                    missing_docs.append(doc_type)

            if missing_docs:
                result["warnings"].append(f"Missing documentation: {', '.join(missing_docs)}")
                result["recommendations"].append("Add missing documentation files")

        except Exception as e:
            result["warnings"].append(f"Could not check documentation: {e}")

    def _check_code_quality(self, repo_path: Path, result: dict[str, Any], fix_issues: bool) -> None:
        """Basic code quality checks.

        Args:
            repo_path: Repository path
            result: Results dictionary to update
            fix_issues: Whether to attempt fixes
        """
        try:
            # Check for .gitignore
            if not (repo_path / ".gitignore").exists():
                result["warnings"].append("No .gitignore file found")
                result["recommendations"].append("Add .gitignore to exclude unnecessary files")

            # Check for configuration files
            config_files = [".editorconfig", ".prettierrc", "eslint.config.js", ".flake8", "pyproject.toml"]

            found_configs = []
            for config_file in config_files:
                if (repo_path / config_file).exists():
                    found_configs.append(config_file)

            if not found_configs:
                result["recommendations"].append("Consider adding code formatting/linting configuration")

        except Exception as e:
            result["warnings"].append(f"Could not check code quality: {e}")

    def _analyze_repository_cleanup(self, repo_path: Path, targets: list[str], dry_run: bool) -> dict[str, Any]:
        """Analyze cleanup opportunities for a repository.

        Args:
            repo_path: Repository path
            targets: Cleanup targets
            dry_run: Whether this is a dry run

        Returns:
            Cleanup analysis results
        """
        cleanup_result = {
            "repository": repo_path.name,
            "repository_path": str(repo_path),
            "cleanup_targets": [],
            "potential_savings_mb": 0,
            "files_to_remove": 0,
        }

        try:
            total_size = 0
            total_files = 0

            for target in targets:
                if "*" in target:
                    # Handle glob patterns
                    matches = list(repo_path.rglob(target))
                else:
                    # Handle directory/file names
                    matches = list(repo_path.rglob(target))

                if matches:
                    target_size = 0
                    target_files = 0

                    for match in matches:
                        if match.is_file():
                            try:
                                target_size += match.stat().st_size
                                target_files += 1
                            except (OSError, PermissionError):
                                pass
                        elif match.is_dir():
                            dir_size, dir_files = self._calculate_directory_stats(match)
                            target_size += dir_size
                            target_files += dir_files

                    if target_size > 0:
                        cleanup_result["cleanup_targets"].append(
                            {
                                "target": target,
                                "matches": len(matches),
                                "size_mb": round(target_size / 1024 / 1024, 2),
                                "files": target_files,
                            }
                        )
                        total_size += target_size
                        total_files += target_files

            cleanup_result["potential_savings_mb"] = round(total_size / 1024 / 1024, 2)
            cleanup_result["files_to_remove"] = total_files

        except Exception as e:
            logger.error(f"Cleanup analysis failed for {repo_path.name}: {e}")
            cleanup_result["error"] = str(e)

        return cleanup_result

    def _execute_cleanup(self, repo_path: str, cleanup_targets: list[dict[str, Any]]) -> None:
        """Execute cleanup operations.

        Args:
            repo_path: Repository path
            cleanup_targets: Targets to clean up
        """
        repo = Path(repo_path)

        for target_info in cleanup_targets:
            target = target_info["target"]

            try:
                if "*" in target:
                    # Handle glob patterns
                    matches = list(repo.rglob(target))
                else:
                    # Handle directory/file names
                    matches = list(repo.rglob(target))

                for match in matches:
                    try:
                        if match.is_file():
                            match.unlink()
                            logger.debug(f"Removed file: {match}")
                        elif match.is_dir():
                            shutil.rmtree(match)
                            logger.debug(f"Removed directory: {match}")
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Could not remove {match}: {e}")

            except Exception as e:
                logger.error(f"Failed to clean up {target} in {repo_path}: {e}")

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate directory size in bytes.

        Args:
            directory: Directory to calculate

        Returns:
            Size in bytes
        """
        total_size = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

        return total_size

    def _calculate_directory_stats(self, directory: Path) -> tuple[int, int]:
        """Calculate directory size and file count.

        Args:
            directory: Directory to calculate

        Returns:
            Tuple of (size_bytes, file_count)
        """
        total_size = 0
        file_count = 0

        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                        file_count += 1
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

        return total_size, file_count

    def _generate_health_recommendations(self, health_results: list[dict[str, Any]]) -> list[str]:
        """Generate health recommendations based on scan results.

        Args:
            health_results: List of repository health results

        Returns:
            List of recommendations
        """
        recommendations = []

        # Count common issues
        repos_with_large_files = sum(1 for result in health_results if "large_files" in result)
        repos_with_cleanup_opportunities = sum(
            1 for result in health_results if result.get("potential_cleanup_mb", 0) > 50
        )
        repos_missing_docs = sum(
            1 for result in health_results if any("documentation" in str(issue) for issue in result.get("warnings", []))
        )

        if repos_with_large_files > 0:
            recommendations.append(f"Consider Git LFS setup for {repos_with_large_files} repositories with large files")

        if repos_with_cleanup_opportunities > 0:
            recommendations.append(
                f"Run cleanup on {repos_with_cleanup_opportunities} repositories to reclaim disk space"
            )

        if repos_missing_docs > 0:
            recommendations.append(f"Add documentation to {repos_missing_docs} repositories")

        if len(health_results) > 10:
            recommendations.append("Consider implementing automated health monitoring for large workspace")

        return recommendations

    def _generate_health_report(self, summary: dict[str, Any], report_path: str) -> None:
        """Generate HTML health report.

        Args:
            summary: Health scan summary
            report_path: Path to save report
        """
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Repository Health Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .repo {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .issues {{ color: #d32f2f; }}
        .warnings {{ color: #f57c00; }}
        .recommendations {{ color: #1976d2; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Repository Health Report</h1>
    <p>Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}</p>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Repositories Scanned:</strong> {summary["summary"]["repositories_scanned"]}</p>
        <p><strong>Total Issues Found:</strong> {summary["summary"]["total_issues_found"]}</p>
        <p><strong>Issues Fixed:</strong> {summary["summary"]["issues_fixed"]}</p>
        <p><strong>Execution Time:</strong> {summary["execution_time_seconds"]} seconds</p>
    </div>

    <h2>Recommendations</h2>
    <ul class="recommendations">
        {"".join(f"<li>{rec}</li>" for rec in summary["recommendations"])}
    </ul>

    <h2>Repository Details</h2>
    {"".join(self._format_health_repo_html(repo) for repo in summary["repositories"])}

</body>
</html>
        """

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Health report saved to {report_path}")
        except OSError as e:
            logger.error(f"Failed to save health report: {e}")

    def _format_health_repo_html(self, repo: dict[str, Any]) -> str:
        """Format repository health data as HTML.

        Args:
            repo: Repository health data

        Returns:
            HTML string for repository
        """
        issues_html = "".join(f"<li class='issues'>{issue}</li>" for issue in repo.get("issues", []))
        warnings_html = "".join(f"<li class='warnings'>{warning}</li>" for warning in repo.get("warnings", []))
        recommendations_html = "".join(
            f"<li class='recommendations'>{rec}</li>" for rec in repo.get("recommendations", [])
        )

        return f"""
        <div class="repo">
            <h3>{repo["repository"]}</h3>
            <p><strong>Path:</strong> {repo["repository_path"]}</p>
            {f"<h4>Issues:</h4><ul>{issues_html}</ul>" if issues_html else ""}
            {f"<h4>Warnings:</h4><ul>{warnings_html}</ul>" if warnings_html else ""}
            {f"<h4>Recommendations:</h4><ul>{recommendations_html}</ul>" if recommendations_html else ""}
            {f"<p><strong>Potential Cleanup:</strong> {repo['potential_cleanup_mb']} MB</p>" if "potential_cleanup_mb" in repo else ""}
        </div>
        """
