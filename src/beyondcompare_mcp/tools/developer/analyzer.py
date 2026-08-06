"""
Development Workspace Analyzer.

Comprehensive analysis tool for development workspaces providing insights
into repository health, languages, dependencies, and optimization opportunities.
"""

import json
import logging
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WorkspaceAnalyzer:
    """Comprehensive development workspace analyzer."""

    # File extensions for different programming languages
    LANGUAGE_EXTENSIONS = {
        "Python": [".py", ".pyx", ".pyi"],
        "JavaScript": [".js", ".jsx", ".mjs"],
        "TypeScript": [".ts", ".tsx"],
        "Java": [".java"],
        "C++": [".cpp", ".cxx", ".cc", ".c"],
        "C#": [".cs"],
        "Go": [".go"],
        "Rust": [".rs"],
        "PHP": [".php"],
        "Ruby": [".rb"],
        "Swift": [".swift"],
        "Kotlin": [".kt", ".kts"],
        "Scala": [".scala"],
        "R": [".r", ".R"],
        "Shell": [".sh", ".bash", ".zsh"],
        "PowerShell": [".ps1", ".psm1"],
        "HTML": [".html", ".htm"],
        "CSS": [".css", ".scss", ".sass", ".less"],
        "SQL": [".sql"],
        "Markdown": [".md", ".markdown"],
        "YAML": [".yml", ".yaml"],
        "JSON": [".json"],
        "XML": [".xml"],
    }

    # Dependency files for different ecosystems
    DEPENDENCY_FILES = {
        "Node.js": ["package.json", "package-lock.json", "yarn.lock"],
        "Python": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
        "Java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "Rust": ["Cargo.toml", "Cargo.lock"],
        "Go": ["go.mod", "go.sum"],
        "C#": ["*.csproj", "*.sln", "packages.config"],
        "PHP": ["composer.json", "composer.lock"],
        "Ruby": ["Gemfile", "Gemfile.lock"],
    }

    def __init__(self, bc_path: Path | None = None):
        """Initialize the workspace analyzer.

        Args:
            bc_path: Path to Beyond Compare executable for advanced analysis
        """
        self.bc_path = bc_path

    def analyze_workspace(
        self,
        workspace_path: str,
        report_path: str | None = None,
        include_git_stats: bool = True,
        include_dependencies: bool = True,
        include_size_analysis: bool = True,
    ) -> dict[str, Any]:
        """Analyze development workspace comprehensively.

        Args:
            workspace_path: Path to development workspace
            report_path: Optional path to save HTML report
            include_git_stats: Include Git repository statistics
            include_dependencies: Analyze dependencies
            include_size_analysis: Calculate disk usage

        Returns:
            Comprehensive workspace analysis
        """
        start_time = time.time()

        try:
            workspace = Path(workspace_path)
            if not workspace.exists():
                raise FileNotFoundError(f"Workspace path does not exist: {workspace}")

            logger.info(f"Analyzing workspace: {workspace}")

            # Find all repositories
            repositories = self._find_repositories(workspace)
            logger.info(f"Found {len(repositories)} repositories")

            # Analyze each repository
            repo_analyses = []
            total_stats = self._initialize_total_stats()

            for repo_path in repositories:
                repo_analysis = self._analyze_repository(
                    repo_path, include_git_stats, include_dependencies, include_size_analysis
                )
                repo_analyses.append(repo_analysis)
                self._update_total_stats(total_stats, repo_analysis)

            # Generate workspace summary
            workspace_summary = self._generate_workspace_summary(workspace, repositories, total_stats)

            # Create comprehensive analysis result
            analysis = {
                "success": True,
                "operation": "analyze_dev_workspace",
                "workspace_path": str(workspace),
                "analysis_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "execution_time_seconds": round(time.time() - start_time, 2),
                "summary": workspace_summary,
                "repositories": repo_analyses,
                "recommendations": self._generate_recommendations(total_stats, repo_analyses),
            }

            # Generate HTML report if requested
            if report_path:
                self._generate_html_report(analysis, report_path)
                analysis["report_path"] = report_path

            return analysis

        except Exception as e:
            logger.error(f"Workspace analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def _find_repositories(self, workspace_path: Path) -> list[Path]:
        """Find all repositories in workspace.

        Args:
            workspace_path: Workspace to search

        Returns:
            List of repository paths
        """
        repositories = []

        try:
            for item in workspace_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    # Check for various project indicators
                    indicators = [
                        ".git",
                        "package.json",
                        "requirements.txt",
                        "Cargo.toml",
                        "pom.xml",
                        "build.gradle",
                        "setup.py",
                        "go.mod",
                        "composer.json",
                    ]

                    if any((item / indicator).exists() for indicator in indicators):
                        repositories.append(item)

        except PermissionError as e:
            logger.warning(f"Permission denied accessing {workspace_path}: {e}")

        return sorted(repositories)

    def _analyze_repository(
        self, repo_path: Path, include_git_stats: bool, include_dependencies: bool, include_size_analysis: bool
    ) -> dict[str, Any]:
        """Analyze a single repository.

        Args:
            repo_path: Repository to analyze
            include_git_stats: Include Git statistics
            include_dependencies: Include dependency analysis
            include_size_analysis: Include size analysis

        Returns:
            Repository analysis results
        """
        analysis = {"name": repo_path.name, "path": str(repo_path), "type": self._detect_repository_type(repo_path)}

        try:
            # Language analysis
            analysis["languages"] = self._analyze_languages(repo_path)

            # Size analysis
            if include_size_analysis:
                analysis["size_analysis"] = self._analyze_repository_size(repo_path)

            # Git statistics
            if include_git_stats and (repo_path / ".git").exists():
                analysis["git_stats"] = self._analyze_git_repository(repo_path)

            # Dependency analysis
            if include_dependencies:
                analysis["dependencies"] = self._analyze_dependencies(repo_path)

            # Last activity
            analysis["last_modified"] = self._get_last_modified_time(repo_path)

            # Health indicators
            analysis["health"] = self._analyze_repository_health(repo_path)

        except Exception as e:
            logger.error(f"Failed to analyze repository {repo_path.name}: {e}")
            analysis["error"] = str(e)

        return analysis

    def _detect_repository_type(self, repo_path: Path) -> str:
        """Detect the type of repository.

        Args:
            repo_path: Repository path

        Returns:
            Repository type string
        """
        # Check for specific project files
        if (repo_path / "package.json").exists():
            return "Node.js"
        elif (repo_path / "requirements.txt").exists() or (repo_path / "setup.py").exists():
            return "Python"
        elif (repo_path / "Cargo.toml").exists():
            return "Rust"
        elif (repo_path / "pom.xml").exists():
            return "Java (Maven)"
        elif (repo_path / "build.gradle").exists():
            return "Java (Gradle)"
        elif (repo_path / "go.mod").exists():
            return "Go"
        elif (repo_path / "composer.json").exists():
            return "PHP"
        elif (repo_path / "Gemfile").exists():
            return "Ruby"
        elif any((repo_path / f).exists() for f in ["*.csproj", "*.sln"]):
            return "C#"
        elif (repo_path / ".git").exists():
            return "Git Repository"
        else:
            return "Unknown"

    def _analyze_languages(self, repo_path: Path) -> dict[str, Any]:
        """Analyze programming languages used in repository.

        Args:
            repo_path: Repository path

        Returns:
            Language analysis results
        """
        language_stats = defaultdict(lambda: {"files": 0, "lines": 0})

        try:
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    extension = file_path.suffix.lower()

                    # Find matching language
                    for language, extensions in self.LANGUAGE_EXTENSIONS.items():
                        if extension in extensions:
                            language_stats[language]["files"] += 1

                            # Count lines (basic implementation)
                            try:
                                with open(file_path, encoding="utf-8", errors="ignore") as f:
                                    lines = sum(1 for line in f if line.strip())
                                    language_stats[language]["lines"] += lines
                            except (OSError, UnicodeDecodeError):
                                pass  # Skip files we can't read
                            break

        except Exception as e:
            logger.warning(f"Language analysis failed for {repo_path}: {e}")

        # Convert to regular dict and calculate percentages
        total_lines = sum(stats["lines"] for stats in language_stats.values())
        result = {}

        for language, stats in language_stats.items():
            percentage = (stats["lines"] / total_lines * 100) if total_lines > 0 else 0
            result[language] = {"files": stats["files"], "lines": stats["lines"], "percentage": round(percentage, 1)}

        return dict(sorted(result.items(), key=lambda x: x[1]["lines"], reverse=True))

    def _analyze_repository_size(self, repo_path: Path) -> dict[str, Any]:
        """Analyze repository size and disk usage.

        Args:
            repo_path: Repository path

        Returns:
            Size analysis results
        """
        try:
            total_size = 0
            file_count = 0
            largest_files = []
            directory_sizes = defaultdict(int)

            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    try:
                        size = file_path.stat().st_size
                        total_size += size
                        file_count += 1

                        # Track largest files
                        largest_files.append((str(file_path.relative_to(repo_path)), size))

                        # Track directory sizes
                        parent_dir = str(file_path.parent.relative_to(repo_path))
                        directory_sizes[parent_dir] += size

                    except (OSError, PermissionError):
                        pass

            # Sort and limit largest files
            largest_files.sort(key=lambda x: x[1], reverse=True)
            largest_files = largest_files[:10]  # Top 10 largest files

            # Sort directory sizes
            sorted_dirs = sorted(directory_sizes.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "file_count": file_count,
                "average_file_size_kb": round((total_size / file_count / 1024), 2) if file_count > 0 else 0,
                "largest_files": [
                    {"path": path, "size_mb": round(size / 1024 / 1024, 2)} for path, size in largest_files
                ],
                "largest_directories": [
                    {"path": path, "size_mb": round(size / 1024 / 1024, 2)} for path, size in sorted_dirs
                ],
            }

        except Exception as e:
            logger.warning(f"Size analysis failed for {repo_path}: {e}")
            return {"error": str(e)}

    def _analyze_git_repository(self, repo_path: Path) -> dict[str, Any]:
        """Analyze Git repository statistics.

        Args:
            repo_path: Repository path

        Returns:
            Git statistics
        """
        try:
            git_stats = {}

            # Get current branch
            try:
                result = subprocess.run(
                    ["git", "branch", "--show-current"], cwd=repo_path, capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    git_stats["current_branch"] = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Get commit count
            try:
                result = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD"], cwd=repo_path, capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    git_stats["commit_count"] = int(result.stdout.strip())
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass

            # Get last commit info
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--format=%H|%an|%ad|%s", "--date=iso"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split("|", 3)
                    if len(parts) == 4:
                        git_stats["last_commit"] = {
                            "hash": parts[0][:8],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3],
                        }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Check for uncommitted changes
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    git_stats["has_uncommitted_changes"] = bool(result.stdout.strip())
                    git_stats["uncommitted_files"] = (
                        len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            return git_stats

        except Exception as e:
            logger.warning(f"Git analysis failed for {repo_path}: {e}")
            return {"error": str(e)}

    def _analyze_dependencies(self, repo_path: Path) -> dict[str, Any]:
        """Analyze project dependencies.

        Args:
            repo_path: Repository path

        Returns:
            Dependency analysis results
        """
        dependencies = {}

        # Check for Node.js dependencies
        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json, encoding="utf-8") as f:
                    data = json.load(f)
                    deps = data.get("dependencies", {})
                    dev_deps = data.get("devDependencies", {})
                    dependencies["Node.js"] = {
                        "dependencies": len(deps),
                        "dev_dependencies": len(dev_deps),
                        "total": len(deps) + len(dev_deps),
                    }
            except (json.JSONDecodeError, OSError):
                pass

        # Check for Python dependencies
        requirements_txt = repo_path / "requirements.txt"
        if requirements_txt.exists():
            try:
                with open(requirements_txt, encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    dependencies["Python"] = {"requirements": len(lines)}
            except OSError:
                pass

        # Check for Rust dependencies
        cargo_toml = repo_path / "Cargo.toml"
        if cargo_toml.exists():
            try:
                with open(cargo_toml, encoding="utf-8") as f:
                    content = f.read()
                    # Simple parsing - count [dependencies] section entries
                    in_deps = False
                    dep_count = 0
                    for line in content.split("\n"):
                        line = line.strip()
                        if line == "[dependencies]":
                            in_deps = True
                        elif line.startswith("[") and line != "[dependencies]":
                            in_deps = False
                        elif in_deps and "=" in line and not line.startswith("#"):
                            dep_count += 1

                    dependencies["Rust"] = {"dependencies": dep_count}
            except OSError:
                pass

        return dependencies

    def _get_last_modified_time(self, repo_path: Path) -> str | None:
        """Get last modification time of repository.

        Args:
            repo_path: Repository path

        Returns:
            Last modification time as ISO string
        """
        try:
            latest_time = 0
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    try:
                        mtime = file_path.stat().st_mtime
                        if mtime > latest_time:
                            latest_time = mtime
                    except (OSError, PermissionError):
                        pass

            if latest_time > 0:
                return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest_time))

        except Exception:
            pass

        return None

    def _analyze_repository_health(self, repo_path: Path) -> dict[str, Any]:
        """Analyze repository health indicators.

        Args:
            repo_path: Repository path

        Returns:
            Health analysis results
        """
        health = {
            "score": 100,  # Start with perfect score
            "issues": [],
            "recommendations": [],
        }

        try:
            # Check for README
            readme_files = list(repo_path.glob("README*"))
            if not readme_files:
                health["score"] -= 10
                health["issues"].append("No README file found")
                health["recommendations"].append("Add a README file to document the project")

            # Check for license
            license_files = list(repo_path.glob("LICENSE*"))
            if not license_files:
                health["score"] -= 5
                health["issues"].append("No LICENSE file found")
                health["recommendations"].append("Add a LICENSE file to clarify usage rights")

            # Check for .gitignore
            if not (repo_path / ".gitignore").exists():
                health["score"] -= 5
                health["issues"].append("No .gitignore file found")
                health["recommendations"].append("Add .gitignore to exclude unnecessary files")

            # Check for large files (>100MB)
            large_files = []
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    try:
                        size_mb = file_path.stat().st_size / 1024 / 1024
                        if size_mb > 100:
                            large_files.append(str(file_path.relative_to(repo_path)))
                    except (OSError, PermissionError):
                        pass

            if large_files:
                health["score"] -= min(20, len(large_files) * 5)
                health["issues"].append(f"Found {len(large_files)} large files (>100MB)")
                health["recommendations"].append("Consider using Git LFS for large files")

            # Check for common build artifacts
            artifact_patterns = ["node_modules", "__pycache__", "target", "dist", "build"]
            found_artifacts = []
            for pattern in artifact_patterns:
                if list(repo_path.glob(f"**/{pattern}")):
                    found_artifacts.append(pattern)

            if found_artifacts:
                health["score"] -= min(15, len(found_artifacts) * 3)
                health["issues"].append(f"Build artifacts found: {', '.join(found_artifacts)}")
                health["recommendations"].append("Update .gitignore to exclude build artifacts")

            health["score"] = max(0, health["score"])  # Don't go below 0

        except Exception as e:
            logger.warning(f"Health analysis failed for {repo_path}: {e}")

        return health

    def _initialize_total_stats(self) -> dict[str, Any]:
        """Initialize total statistics structure.

        Returns:
            Empty statistics structure
        """
        return {
            "total_repositories": 0,
            "total_size_mb": 0,
            "total_files": 0,
            "languages": defaultdict(lambda: {"files": 0, "lines": 0}),
            "repository_types": defaultdict(int),
            "health_scores": [],
            "git_repositories": 0,
            "repositories_with_issues": 0,
        }

    def _update_total_stats(self, total_stats: dict[str, Any], repo_analysis: dict[str, Any]) -> None:
        """Update total statistics with repository analysis.

        Args:
            total_stats: Total statistics to update
            repo_analysis: Repository analysis to add
        """
        total_stats["total_repositories"] += 1

        # Update size statistics
        if "size_analysis" in repo_analysis:
            size_analysis = repo_analysis["size_analysis"]
            if "total_size_mb" in size_analysis:
                total_stats["total_size_mb"] += size_analysis["total_size_mb"]
            if "file_count" in size_analysis:
                total_stats["total_files"] += size_analysis["file_count"]

        # Update language statistics
        if "languages" in repo_analysis:
            for language, stats in repo_analysis["languages"].items():
                total_stats["languages"][language]["files"] += stats["files"]
                total_stats["languages"][language]["lines"] += stats["lines"]

        # Update repository types
        if "type" in repo_analysis:
            total_stats["repository_types"][repo_analysis["type"]] += 1

        # Update health statistics
        if "health" in repo_analysis:
            health = repo_analysis["health"]
            if "score" in health:
                total_stats["health_scores"].append(health["score"])
            if health.get("issues"):
                total_stats["repositories_with_issues"] += 1

        # Update Git statistics
        if "git_stats" in repo_analysis:
            total_stats["git_repositories"] += 1

    def _generate_workspace_summary(
        self, workspace: Path, repositories: list[Path], total_stats: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate workspace summary statistics.

        Args:
            workspace: Workspace path
            repositories: List of repositories
            total_stats: Total statistics

        Returns:
            Workspace summary
        """
        # Calculate language percentages
        total_lines = sum(stats["lines"] for stats in total_stats["languages"].values())
        language_summary = {}
        for language, stats in total_stats["languages"].items():
            percentage = (stats["lines"] / total_lines * 100) if total_lines > 0 else 0
            language_summary[language] = {
                "files": stats["files"],
                "lines": stats["lines"],
                "percentage": round(percentage, 1),
            }

        # Sort languages by lines of code
        language_summary = dict(sorted(language_summary.items(), key=lambda x: x[1]["lines"], reverse=True))

        # Calculate average health score
        health_scores = total_stats["health_scores"]
        average_health = sum(health_scores) / len(health_scores) if health_scores else 0

        return {
            "workspace_path": str(workspace),
            "total_repositories": total_stats["total_repositories"],
            "total_size_mb": round(total_stats["total_size_mb"], 2),
            "total_files": total_stats["total_files"],
            "git_repositories": total_stats["git_repositories"],
            "repositories_with_issues": total_stats["repositories_with_issues"],
            "average_health_score": round(average_health, 1),
            "languages": language_summary,
            "repository_types": dict(total_stats["repository_types"]),
        }

    def _generate_recommendations(self, total_stats: dict[str, Any], repo_analyses: list[dict[str, Any]]) -> list[str]:
        """Generate optimization recommendations.

        Args:
            total_stats: Total statistics
            repo_analyses: Repository analyses

        Returns:
            List of recommendations
        """
        recommendations = []

        # Size-based recommendations
        if total_stats["total_size_mb"] > 10000:  # >10GB
            recommendations.append("Consider implementing regular cleanup of build artifacts to reduce disk usage")

        # Health-based recommendations
        health_scores = total_stats["health_scores"]
        if health_scores:
            avg_health = sum(health_scores) / len(health_scores)
            if avg_health < 80:
                recommendations.append(
                    "Multiple repositories have health issues - consider standardizing project structure"
                )

        # Git-based recommendations
        git_ratio = total_stats["git_repositories"] / total_stats["total_repositories"]
        if git_ratio < 0.8:
            recommendations.append("Consider initializing Git repositories for better version control")

        # Language diversity recommendations
        if len(total_stats["languages"]) > 10:
            recommendations.append("High language diversity detected - consider consolidating similar projects")

        # Repository-specific recommendations
        repos_with_large_files = sum(
            1 for repo in repo_analyses if "health" in repo and "large files" in str(repo["health"].get("issues", []))
        )
        if repos_with_large_files > 0:
            recommendations.append(f"Found {repos_with_large_files} repositories with large files - consider Git LFS")

        return recommendations

    def _generate_html_report(self, analysis: dict[str, Any], report_path: str) -> None:
        """Generate HTML report from analysis.

        Args:
            analysis: Analysis results
            report_path: Path to save HTML report
        """
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Workspace Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .repo {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .health-good {{ background: #d4edda; }}
        .health-warning {{ background: #fff3cd; }}
        .health-danger {{ background: #f8d7da; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Development Workspace Analysis</h1>
    <p>Generated: {analysis["analysis_time"]}</p>

    <div class="summary">
        <h2>Workspace Summary</h2>
        <p><strong>Path:</strong> {analysis["summary"]["workspace_path"]}</p>
        <p><strong>Repositories:</strong> {analysis["summary"]["total_repositories"]}</p>
        <p><strong>Total Size:</strong> {analysis["summary"]["total_size_mb"]} MB</p>
        <p><strong>Total Files:</strong> {analysis["summary"]["total_files"]}</p>
        <p><strong>Average Health Score:</strong> {analysis["summary"]["average_health_score"]}/100</p>
    </div>

    <h2>Languages</h2>
    <table>
        <tr><th>Language</th><th>Files</th><th>Lines</th><th>Percentage</th></tr>
        {
            "".join(
                f"<tr><td>{lang}</td><td>{stats['files']}</td><td>{stats['lines']}</td><td>{stats['percentage']}%</td></tr>"
                for lang, stats in analysis["summary"]["languages"].items()
            )
        }
    </table>

    <h2>Repository Types</h2>
    <table>
        <tr><th>Type</th><th>Count</th></tr>
        {
            "".join(
                f"<tr><td>{repo_type}</td><td>{count}</td></tr>"
                for repo_type, count in analysis["summary"]["repository_types"].items()
            )
        }
    </table>

    <h2>Recommendations</h2>
    <ul>
        {"".join(f"<li>{rec}</li>" for rec in analysis["recommendations"])}
    </ul>

    <h2>Repository Details</h2>
    {"".join(self._format_repo_html(repo) for repo in analysis["repositories"])}

</body>
</html>
        """

        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"HTML report saved to {report_path}")
        except OSError as e:
            logger.error(f"Failed to save HTML report: {e}")

    def _format_repo_html(self, repo: dict[str, Any]) -> str:
        """Format repository data as HTML.

        Args:
            repo: Repository analysis data

        Returns:
            HTML string for repository
        """
        health_score = repo.get("health", {}).get("score", 0)
        health_class = (
            "health-good" if health_score >= 80 else "health-warning" if health_score >= 60 else "health-danger"
        )

        return f"""
        <div class="repo {health_class}">
            <h3>{repo["name"]} ({repo["type"]})</h3>
            <p><strong>Path:</strong> {repo["path"]}</p>
            <p><strong>Health Score:</strong> {health_score}/100</p>
            {f"<p><strong>Size:</strong> {repo['size_analysis']['total_size_mb']} MB ({repo['size_analysis']['file_count']} files)</p>" if "size_analysis" in repo else ""}
            {f"<p><strong>Last Modified:</strong> {repo['last_modified']}</p>" if repo.get("last_modified") else ""}
            {f"<p><strong>Git Branch:</strong> {repo['git_stats'].get('current_branch', 'N/A')}</p>" if "git_stats" in repo else ""}
        </div>
        """
