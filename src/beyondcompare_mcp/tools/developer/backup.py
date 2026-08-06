"""
Developer Repository Backup Tool.

Smart backup system for development repositories with intelligent filtering,
compression, and incremental backup capabilities.
"""

import json
import logging
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DevRepositoryBackup:
    """Smart backup system for development repositories."""

    # Default patterns to exclude from backups
    DEFAULT_EXCLUDE_PATTERNS = [
        "node_modules/**",
        ".git/objects/**",  # Keep .git but skip large objects
        "target/**",  # Rust/Java build directories
        "dist/**",
        "build/**",  # Build outputs
        "*.log",
        "*.tmp",  # Temporary files
        "__pycache__/**",  # Python cache
        ".pytest_cache/**",  # Pytest cache
        "coverage/**",  # Coverage reports
        ".vscode/**",  # VS Code settings
        ".idea/**",  # IntelliJ settings
        "*.pyc",
        "*.pyo",  # Python compiled files
        ".DS_Store",  # macOS files
        "Thumbs.db",  # Windows files
        "*.swp",
        "*.swo",  # Vim swap files
        ".env",  # Environment files (security)
        ".env.local",  # Local environment files
    ]

    # Essential Git files to preserve
    GIT_ESSENTIALS = [
        ".git/config",
        ".git/HEAD",
        ".git/refs/**",
        ".git/hooks/**",
        ".git/info/**",
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
    ]

    def __init__(self, bc_path: Path | None = None):
        """Initialize the repository backup tool.

        Args:
            bc_path: Path to Beyond Compare executable for advanced comparisons
        """
        self.bc_path = bc_path

    def backup_repositories(
        self,
        source_path: str,
        backup_path: str,
        exclude_patterns: list[str] | None = None,
        include_git_essentials: bool = True,
        compress: bool = True,
        incremental: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Smart backup of development repositories.

        Args:
            source_path: Path to development workspace
            backup_path: Destination for backup files
            exclude_patterns: Additional patterns to exclude
            include_git_essentials: Keep essential Git files
            compress: Create compressed archives
            incremental: Only backup changed repositories
            dry_run: Preview operations without executing

        Returns:
            Backup summary with statistics and operation details
        """
        start_time = time.time()

        try:
            source = Path(source_path)
            backup = Path(backup_path)

            if not source.exists():
                raise FileNotFoundError(f"Source path does not exist: {source}")

            # Prepare exclusion patterns
            all_exclude_patterns = self.DEFAULT_EXCLUDE_PATTERNS.copy()
            if exclude_patterns:
                all_exclude_patterns.extend(exclude_patterns)

            # Find all repositories
            repositories = self._find_repositories(source)
            logger.info(f"Found {len(repositories)} repositories in {source}")

            # Filter repositories for incremental backup
            if incremental:
                repositories = self._filter_changed_repositories(repositories, backup, dry_run)
                logger.info(f"Incremental backup: {len(repositories)} repositories need backup")

            # Create backup directory
            if not dry_run:
                backup.mkdir(parents=True, exist_ok=True)

            # Backup each repository
            backup_results = []
            total_original_size = 0
            total_backup_size = 0

            for repo_path in repositories:
                repo_result = self._backup_single_repository(
                    repo_path, backup, all_exclude_patterns, include_git_essentials, compress, dry_run
                )
                backup_results.append(repo_result)
                total_original_size += repo_result.get("original_size_mb", 0)
                total_backup_size += repo_result.get("backup_size_mb", 0)

            # Calculate statistics
            execution_time = time.time() - start_time
            space_saved_mb = total_original_size - total_backup_size
            compression_ratio = (space_saved_mb / total_original_size * 100) if total_original_size > 0 else 0

            # Generate summary
            summary = {
                "success": True,
                "operation": "backup_dev_repositories",
                "dry_run": dry_run,
                "statistics": {
                    "repositories_found": len(self._find_repositories(source)),
                    "repositories_backed_up": len(repositories),
                    "total_original_size_mb": round(total_original_size, 2),
                    "total_backup_size_mb": round(total_backup_size, 2),
                    "space_saved_mb": round(space_saved_mb, 2),
                    "compression_ratio_percent": round(compression_ratio, 1),
                    "execution_time_seconds": round(execution_time, 2),
                },
                "settings": {
                    "source_path": str(source),
                    "backup_path": str(backup),
                    "compress": compress,
                    "incremental": incremental,
                    "include_git_essentials": include_git_essentials,
                    "exclude_patterns_count": len(all_exclude_patterns),
                },
                "repositories": backup_results,
            }

            # Save backup manifest
            if not dry_run:
                manifest_path = backup / "backup_manifest.json"
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2, default=str)
                logger.info(f"Backup manifest saved to {manifest_path}")

            return summary

        except Exception as e:
            logger.error(f"Repository backup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def _find_repositories(self, workspace_path: Path) -> list[Path]:
        """Find all repositories in the workspace.

        Args:
            workspace_path: Path to search for repositories

        Returns:
            List of repository paths
        """
        repositories = []

        try:
            for item in workspace_path.iterdir():
                if item.is_dir():
                    # Check if it's a Git repository
                    if (item / ".git").exists():
                        repositories.append(item)
                    # Check if it contains package.json (Node.js project)
                    elif (item / "package.json").exists():
                        repositories.append(item)
                    # Check if it contains requirements.txt (Python project)
                    elif (item / "requirements.txt").exists():
                        repositories.append(item)
                    # Check if it contains Cargo.toml (Rust project)
                    elif (item / "Cargo.toml").exists():
                        repositories.append(item)
                    # Check if it contains pom.xml (Maven project)
                    elif (item / "pom.xml").exists():
                        repositories.append(item)
                    # Check if it contains build.gradle (Gradle project)
                    elif (item / "build.gradle").exists() or (item / "build.gradle.kts").exists():
                        repositories.append(item)

        except PermissionError as e:
            logger.warning(f"Permission denied accessing {workspace_path}: {e}")

        return sorted(repositories)

    def _filter_changed_repositories(self, repositories: list[Path], backup_path: Path, dry_run: bool) -> list[Path]:
        """Filter repositories that need backup based on changes.

        Args:
            repositories: List of repository paths
            backup_path: Backup destination path
            dry_run: Whether this is a dry run

        Returns:
            List of repositories that need backup
        """
        if not backup_path.exists():
            return repositories  # First backup, include all

        changed_repos = []

        for repo in repositories:
            repo_backup_path = backup_path / f"{repo.name}.zip"

            # If backup doesn't exist, include it
            if not repo_backup_path.exists():
                changed_repos.append(repo)
                continue

            # Check if repository has been modified since last backup
            try:
                backup_time = repo_backup_path.stat().st_mtime

                # Check if any files in the repository are newer than backup
                has_newer_files = False
                for file_path in repo.rglob("*"):
                    if file_path.is_file() and file_path.stat().st_mtime > backup_time:
                        # Skip files that would be excluded anyway
                        if not self._should_exclude_file(file_path, repo, self.DEFAULT_EXCLUDE_PATTERNS):
                            has_newer_files = True
                            break

                if has_newer_files:
                    changed_repos.append(repo)

            except (OSError, PermissionError) as e:
                logger.warning(f"Could not check modification time for {repo}: {e}")
                changed_repos.append(repo)  # Include on error to be safe

        return changed_repos

    def _backup_single_repository(
        self,
        repo_path: Path,
        backup_path: Path,
        exclude_patterns: list[str],
        include_git_essentials: bool,
        compress: bool,
        dry_run: bool,
    ) -> dict[str, Any]:
        """Backup a single repository.

        Args:
            repo_path: Path to repository to backup
            backup_path: Backup destination path
            exclude_patterns: Patterns to exclude
            include_git_essentials: Include essential Git files
            compress: Create compressed archive
            dry_run: Preview without executing

        Returns:
            Backup result for this repository
        """
        start_time = time.time()

        try:
            # Calculate original size
            original_size = self._calculate_directory_size(repo_path)

            # Determine backup destination
            backup_name = f"{repo_path.name}.zip" if compress else repo_path.name
            repo_backup_path = backup_path / backup_name

            if dry_run:
                # For dry run, estimate backup size
                estimated_size = self._estimate_backup_size(repo_path, exclude_patterns, include_git_essentials)
                return {
                    "repository": repo_path.name,
                    "status": "would_backup",
                    "original_size_mb": round(original_size / 1024 / 1024, 2),
                    "backup_size_mb": round(estimated_size / 1024 / 1024, 2),
                    "backup_path": str(repo_backup_path),
                    "execution_time_seconds": round(time.time() - start_time, 2),
                }

            # Perform actual backup
            if compress:
                backup_size = self._create_compressed_backup(
                    repo_path, repo_backup_path, exclude_patterns, include_git_essentials
                )
            else:
                backup_size = self._create_directory_backup(
                    repo_path, repo_backup_path, exclude_patterns, include_git_essentials
                )

            return {
                "repository": repo_path.name,
                "status": "backed_up",
                "original_size_mb": round(original_size / 1024 / 1024, 2),
                "backup_size_mb": round(backup_size / 1024 / 1024, 2),
                "backup_path": str(repo_backup_path),
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

        except Exception as e:
            logger.error(f"Failed to backup repository {repo_path.name}: {e}")
            return {
                "repository": repo_path.name,
                "status": "failed",
                "error": str(e),
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def _create_compressed_backup(
        self, repo_path: Path, backup_path: Path, exclude_patterns: list[str], include_git_essentials: bool
    ) -> int:
        """Create compressed ZIP backup of repository.

        Args:
            repo_path: Repository to backup
            backup_path: Backup file path
            exclude_patterns: Patterns to exclude
            include_git_essentials: Include essential Git files

        Returns:
            Size of backup file in bytes
        """
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    if self._should_include_file(file_path, repo_path, exclude_patterns, include_git_essentials):
                        relative_path = file_path.relative_to(repo_path)
                        try:
                            zipf.write(file_path, relative_path)
                        except (OSError, PermissionError) as e:
                            logger.warning(f"Could not add {file_path} to backup: {e}")

        return backup_path.stat().st_size

    def _create_directory_backup(
        self, repo_path: Path, backup_path: Path, exclude_patterns: list[str], include_git_essentials: bool
    ) -> int:
        """Create directory backup of repository.

        Args:
            repo_path: Repository to backup
            backup_path: Backup directory path
            exclude_patterns: Patterns to exclude
            include_git_essentials: Include essential Git files

        Returns:
            Size of backup directory in bytes
        """
        backup_path.mkdir(parents=True, exist_ok=True)

        for file_path in repo_path.rglob("*"):
            if file_path.is_file():
                if self._should_include_file(file_path, repo_path, exclude_patterns, include_git_essentials):
                    relative_path = file_path.relative_to(repo_path)
                    target_path = backup_path / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(file_path, target_path)
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Could not copy {file_path} to backup: {e}")

        return self._calculate_directory_size(backup_path)

    def _should_include_file(
        self, file_path: Path, repo_path: Path, exclude_patterns: list[str], include_git_essentials: bool
    ) -> bool:
        """Determine if a file should be included in backup.

        Args:
            file_path: File to check
            repo_path: Repository root path
            exclude_patterns: Patterns to exclude
            include_git_essentials: Include essential Git files

        Returns:
            True if file should be included
        """
        relative_path = file_path.relative_to(repo_path)
        relative_str = str(relative_path).replace("\\", "/")

        # Check if it's an essential Git file
        if include_git_essentials and relative_str.startswith(".git/"):
            for essential_pattern in self.GIT_ESSENTIALS:
                if self._matches_pattern(relative_str, essential_pattern):
                    return True

        # Check exclusion patterns
        return not self._should_exclude_file(file_path, repo_path, exclude_patterns)

    def _should_exclude_file(self, file_path: Path, repo_path: Path, exclude_patterns: list[str]) -> bool:
        """Check if file should be excluded from backup.

        Args:
            file_path: File to check
            repo_path: Repository root path
            exclude_patterns: Patterns to exclude

        Returns:
            True if file should be excluded
        """
        relative_path = file_path.relative_to(repo_path)
        relative_str = str(relative_path).replace("\\", "/")

        for pattern in exclude_patterns:
            if self._matches_pattern(relative_str, pattern):
                return True

        return False

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches exclusion pattern.

        Args:
            path: File path to check
            pattern: Pattern to match against

        Returns:
            True if path matches pattern
        """
        import fnmatch

        # Handle directory patterns ending with /**
        if pattern.endswith("/**"):
            dir_pattern = pattern[:-3]
            if path.startswith(dir_pattern + "/") or path == dir_pattern:
                return True

        # Handle glob patterns
        return fnmatch.fnmatch(path, pattern)

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes.

        Args:
            directory: Directory to calculate size for

        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except (OSError, PermissionError):
                        pass  # Skip files we can't access
        except (OSError, PermissionError):
            pass  # Skip directories we can't access

        return total_size

    def _estimate_backup_size(self, repo_path: Path, exclude_patterns: list[str], include_git_essentials: bool) -> int:
        """Estimate backup size for dry run.

        Args:
            repo_path: Repository path
            exclude_patterns: Patterns to exclude
            include_git_essentials: Include essential Git files

        Returns:
            Estimated backup size in bytes
        """
        estimated_size = 0

        for file_path in repo_path.rglob("*"):
            if file_path.is_file():
                if self._should_include_file(file_path, repo_path, exclude_patterns, include_git_essentials):
                    try:
                        estimated_size += file_path.stat().st_size
                    except (OSError, PermissionError):
                        pass

        # Estimate compression (typically 30-50% for source code)
        return int(estimated_size * 0.6)  # Assume 40% compression
