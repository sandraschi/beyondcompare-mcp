"""
Code Duplicate Detection and Analysis Tools.

Advanced tools for detecting duplicate code across repositories
and analyzing code similarity for refactoring opportunities.
"""

import hashlib
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeDuplicateDetector:
    """Advanced code duplicate detection and analysis."""

    # Default file types for analysis
    DEFAULT_FILE_TYPES = [
        "*.py",
        "*.js",
        "*.ts",
        "*.jsx",
        "*.tsx",
        "*.java",
        "*.cpp",
        "*.c",
        "*.cs",
        "*.go",
        "*.rs",
        "*.php",
        "*.rb",
        "*.swift",
        "*.kt",
    ]

    def __init__(self, bc_path: Path | None = None):
        """Initialize the duplicate detector.

        Args:
            bc_path: Path to Beyond Compare executable
        """
        self.bc_path = bc_path

    def find_duplicate_code(
        self,
        repos_path: str,
        file_types: list[str] | None = None,
        min_lines: int = 10,
        similarity_threshold: float = 0.8,
        report_path: str | None = None,
    ) -> dict[str, Any]:
        """Find duplicate code across repositories.

        Args:
            repos_path: Path to repositories directory
            file_types: File extensions to analyze
            min_lines: Minimum lines for duplicate detection
            similarity_threshold: Similarity threshold (0.0-1.0)
            report_path: Optional path to save report

        Returns:
            Duplicate code analysis results
        """
        start_time = time.time()

        try:
            repos_dir = Path(repos_path)
            if not repos_dir.exists():
                raise FileNotFoundError(f"Repository path does not exist: {repos_dir}")

            # Use default file types if none specified
            if file_types is None:
                file_types = self.DEFAULT_FILE_TYPES.copy()

            logger.info(f"Analyzing code duplicates in {repos_dir}")

            # Find all code files
            code_files = self._find_code_files(repos_dir, file_types)
            logger.info(f"Found {len(code_files)} code files to analyze")

            # Extract code blocks
            code_blocks = self._extract_code_blocks(code_files, min_lines)
            logger.info(f"Extracted {len(code_blocks)} code blocks")

            # Find duplicates
            duplicates = self._find_duplicates(code_blocks, similarity_threshold)
            logger.info(f"Found {len(duplicates)} duplicate groups")

            # Analyze duplicate statistics
            duplicate_stats = self._analyze_duplicate_stats(duplicates, code_blocks)

            # Generate result
            result = {
                "success": True,
                "operation": "find_duplicate_code",
                "execution_time_seconds": round(time.time() - start_time, 2),
                "analysis_settings": {
                    "repos_path": str(repos_dir),
                    "file_types": file_types,
                    "min_lines": min_lines,
                    "similarity_threshold": similarity_threshold,
                },
                "statistics": {
                    "total_files_analyzed": len(code_files),
                    "total_code_blocks": len(code_blocks),
                    "duplicate_groups": len(duplicates),
                    "total_duplicate_blocks": duplicate_stats["total_duplicate_blocks"],
                    "total_duplicate_lines": duplicate_stats["total_duplicate_lines"],
                    "potential_refactoring_savings": duplicate_stats["potential_savings"],
                },
                "duplicates": duplicates,
                "recommendations": self._generate_duplicate_recommendations(duplicates, duplicate_stats),
            }

            # Generate report if requested
            if report_path:
                self._generate_duplicate_report(result, report_path)
                result["report_path"] = report_path

            return result

        except Exception as e:
            logger.error(f"Duplicate code analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def compare_workspace_snapshots(
        self,
        snapshot1_path: str,
        snapshot2_path: str,
        report_path: str | None = None,
        show_changes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compare workspace snapshots to identify changes.

        Args:
            snapshot1_path: Path to first snapshot (older)
            snapshot2_path: Path to second snapshot (newer)
            report_path: Optional path to save report
            show_changes: Types of changes to include

        Returns:
            Detailed snapshot comparison
        """
        start_time = time.time()

        try:
            snapshot1 = Path(snapshot1_path)
            snapshot2 = Path(snapshot2_path)

            if not snapshot1.exists():
                raise FileNotFoundError(f"Snapshot 1 does not exist: {snapshot1}")
            if not snapshot2.exists():
                raise FileNotFoundError(f"Snapshot 2 does not exist: {snapshot2}")

            # Default change types to show
            if show_changes is None:
                show_changes = ["new_repos", "deleted_repos", "modified_repos", "size_changes"]

            logger.info(f"Comparing snapshots: {snapshot1} vs {snapshot2}")

            # Analyze both snapshots
            snapshot1_analysis = self._analyze_snapshot(snapshot1)
            snapshot2_analysis = self._analyze_snapshot(snapshot2)

            # Compare snapshots
            comparison = self._compare_snapshots(snapshot1_analysis, snapshot2_analysis, show_changes)

            # Generate result
            result = {
                "success": True,
                "operation": "compare_workspace_snapshots",
                "execution_time_seconds": round(time.time() - start_time, 2),
                "snapshots": {
                    "snapshot1": {
                        "path": str(snapshot1),
                        "repositories": len(snapshot1_analysis["repositories"]),
                        "total_size_mb": snapshot1_analysis["total_size_mb"],
                        "analysis_time": snapshot1_analysis["timestamp"],
                    },
                    "snapshot2": {
                        "path": str(snapshot2),
                        "repositories": len(snapshot2_analysis["repositories"]),
                        "total_size_mb": snapshot2_analysis["total_size_mb"],
                        "analysis_time": snapshot2_analysis["timestamp"],
                    },
                },
                "comparison": comparison,
                "show_changes": show_changes,
            }

            # Generate report if requested
            if report_path:
                self._generate_snapshot_report(result, report_path)
                result["report_path"] = report_path

            return result

        except Exception as e:
            logger.error(f"Workspace snapshot comparison failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def selective_restore(
        self,
        backup_path: str,
        restore_items: list[str],
        target_path: str,
        preserve_structure: bool = True,
        overwrite_existing: bool = False,
    ) -> dict[str, Any]:
        """Selectively restore items from backup.

        Args:
            backup_path: Path to backup location
            restore_items: List of patterns to restore
            target_path: Destination for restored items
            preserve_structure: Maintain directory structure
            overwrite_existing: Overwrite existing files

        Returns:
            Restore operation results
        """
        start_time = time.time()

        try:
            backup_dir = Path(backup_path)
            target_dir = Path(target_path)

            if not backup_dir.exists():
                raise FileNotFoundError(f"Backup path does not exist: {backup_dir}")

            logger.info(f"Selective restore from {backup_dir} to {target_dir}")

            # Find matching items in backup
            matching_items = self._find_restore_matches(backup_dir, restore_items)
            logger.info(f"Found {len(matching_items)} items to restore")

            # Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)

            # Restore items
            restore_results = []
            total_restored = 0
            total_size = 0
            conflicts = []

            for item_path, item_info in matching_items.items():
                restore_result = self._restore_item(
                    item_path, item_info, target_dir, preserve_structure, overwrite_existing
                )
                restore_results.append(restore_result)

                if restore_result["status"] == "restored":
                    total_restored += 1
                    total_size += restore_result.get("size_bytes", 0)
                elif restore_result["status"] == "conflict":
                    conflicts.append(restore_result)

            # Generate result
            result = {
                "success": True,
                "operation": "selective_restore",
                "execution_time_seconds": round(time.time() - start_time, 2),
                "restore_settings": {
                    "backup_path": str(backup_dir),
                    "target_path": str(target_dir),
                    "restore_patterns": restore_items,
                    "preserve_structure": preserve_structure,
                    "overwrite_existing": overwrite_existing,
                },
                "summary": {
                    "items_found": len(matching_items),
                    "items_restored": total_restored,
                    "conflicts": len(conflicts),
                    "total_size_mb": round(total_size / 1024 / 1024, 2),
                },
                "restore_results": restore_results,
                "conflicts": conflicts,
            }

            return result

        except Exception as e:
            logger.error(f"Selective restore failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_seconds": round(time.time() - start_time, 2),
            }

    def _find_code_files(self, repos_dir: Path, file_types: list[str]) -> list[Path]:
        """Find all code files matching the specified types.

        Args:
            repos_dir: Directory to search
            file_types: File type patterns

        Returns:
            List of code file paths
        """
        code_files = []

        try:
            for file_type in file_types:
                code_files.extend(repos_dir.rglob(file_type))

            # Filter out files in common ignore directories
            ignore_dirs = {
                "node_modules",
                "__pycache__",
                ".git",
                "target",
                "dist",
                "build",
                ".pytest_cache",
                "coverage",
            }

            filtered_files = []
            for file_path in code_files:
                if file_path.is_file() and not any(ignore_dir in file_path.parts for ignore_dir in ignore_dirs):
                    filtered_files.append(file_path)

            return filtered_files

        except Exception as e:
            logger.error(f"Failed to find code files: {e}")
            return []

    def _extract_code_blocks(self, code_files: list[Path], min_lines: int) -> list[dict[str, Any]]:
        """Extract code blocks from files for duplicate analysis.

        Args:
            code_files: List of code files
            min_lines: Minimum lines per block

        Returns:
            List of code blocks with metadata
        """
        code_blocks = []

        for file_path in code_files:
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                # Extract blocks of code (functions, classes, etc.)
                blocks = self._extract_blocks_from_lines(lines, min_lines)

                for block_start, block_end, block_lines in blocks:
                    # Normalize code for comparison
                    normalized_code = self._normalize_code(block_lines)
                    code_hash = hashlib.md5(normalized_code.encode()).hexdigest()

                    code_blocks.append(
                        {
                            "file_path": str(file_path),
                            "start_line": block_start,
                            "end_line": block_end,
                            "lines": block_lines,
                            "normalized_code": normalized_code,
                            "hash": code_hash,
                            "line_count": len(block_lines),
                        }
                    )

            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read file {file_path}: {e}")

        return code_blocks

    def _extract_blocks_from_lines(self, lines: list[str], min_lines: int) -> list[tuple[int, int, list[str]]]:
        """Extract code blocks from file lines.

        Args:
            lines: File lines
            min_lines: Minimum lines per block

        Returns:
            List of (start_line, end_line, block_lines) tuples
        """
        blocks = []

        # Simple block extraction using sliding window
        for i in range(len(lines) - min_lines + 1):
            block_lines = lines[i : i + min_lines]

            # Skip blocks that are mostly comments or empty lines
            non_trivial_lines = [
                line
                for line in block_lines
                if line.strip() and not line.strip().startswith(("#", "//", "/*", "*", '"""', "'''"))
            ]

            if len(non_trivial_lines) >= min_lines * 0.6:  # At least 60% non-trivial content
                blocks.append((i + 1, i + min_lines, block_lines))

        return blocks

    def _normalize_code(self, lines: list[str]) -> str:
        """Normalize code for comparison.

        Args:
            lines: Code lines

        Returns:
            Normalized code string
        """
        normalized_lines = []

        for line in lines:
            # Remove leading/trailing whitespace
            normalized = line.strip()

            # Skip empty lines and comments
            if not normalized or normalized.startswith(("#", "//", "/*", "*")):
                continue

            # Normalize whitespace
            normalized = re.sub(r"\s+", " ", normalized)

            # Remove variable names (basic approach)
            # This is a simplified normalization - could be enhanced
            normalized = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", "VAR", normalized)

            normalized_lines.append(normalized)

        return "\n".join(normalized_lines)

    def _find_duplicates(self, code_blocks: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
        """Find duplicate code blocks.

        Args:
            code_blocks: List of code blocks
            threshold: Similarity threshold

        Returns:
            List of duplicate groups
        """
        # Group by hash for exact duplicates
        hash_groups = defaultdict(list)
        for block in code_blocks:
            hash_groups[block["hash"]].append(block)

        duplicates = []

        # Find exact duplicates
        for _code_hash, blocks in hash_groups.items():
            if len(blocks) > 1:
                duplicate_group = {
                    "type": "exact",
                    "similarity": 1.0,
                    "blocks": blocks,
                    "line_count": blocks[0]["line_count"],
                    "total_duplicates": len(blocks),
                    "files_affected": list(set(block["file_path"] for block in blocks)),
                }
                duplicates.append(duplicate_group)

        # For similar (but not exact) duplicates, we'd need more sophisticated analysis
        # This is a simplified implementation focusing on exact matches

        return sorted(duplicates, key=lambda x: x["total_duplicates"] * x["line_count"], reverse=True)

    def _analyze_duplicate_stats(
        self, duplicates: list[dict[str, Any]], all_blocks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze duplicate statistics.

        Args:
            duplicates: List of duplicate groups
            all_blocks: All code blocks

        Returns:
            Duplicate statistics
        """
        total_duplicate_blocks = sum(group["total_duplicates"] for group in duplicates)
        total_duplicate_lines = sum(group["total_duplicates"] * group["line_count"] for group in duplicates)

        # Estimate potential savings (lines that could be refactored)
        potential_savings = sum((group["total_duplicates"] - 1) * group["line_count"] for group in duplicates)

        return {
            "total_duplicate_blocks": total_duplicate_blocks,
            "total_duplicate_lines": total_duplicate_lines,
            "potential_savings": potential_savings,
            "duplicate_percentage": round((total_duplicate_blocks / len(all_blocks) * 100), 1) if all_blocks else 0,
        }

    def _generate_duplicate_recommendations(self, duplicates: list[dict[str, Any]], stats: dict[str, Any]) -> list[str]:
        """Generate recommendations based on duplicate analysis.

        Args:
            duplicates: Duplicate groups
            stats: Duplicate statistics

        Returns:
            List of recommendations
        """
        recommendations = []

        if stats["potential_savings"] > 100:
            recommendations.append(
                f"Consider refactoring - potential to eliminate {stats['potential_savings']} duplicate lines"
            )

        large_duplicates = [d for d in duplicates if d["line_count"] > 50]
        if large_duplicates:
            recommendations.append(
                f"Found {len(large_duplicates)} large duplicate blocks (>50 lines) - high refactoring priority"
            )

        cross_repo_duplicates = [
            d for d in duplicates if len(set(Path(f).parent.name for f in d["files_affected"])) > 1
        ]
        if cross_repo_duplicates:
            recommendations.append(
                f"Found {len(cross_repo_duplicates)} cross-repository duplicates - consider shared libraries"
            )

        if stats["duplicate_percentage"] > 15:
            recommendations.append("High duplicate percentage detected - consider code review and refactoring strategy")

        return recommendations

    def _analyze_snapshot(self, snapshot_path: Path) -> dict[str, Any]:
        """Analyze a workspace snapshot.

        Args:
            snapshot_path: Path to snapshot

        Returns:
            Snapshot analysis
        """
        repositories = {}
        total_size = 0

        try:
            for item in snapshot_path.iterdir():
                if item.is_dir():
                    repo_size = self._calculate_directory_size(item)
                    repositories[item.name] = {
                        "path": str(item),
                        "size_mb": round(repo_size / 1024 / 1024, 2),
                        "last_modified": item.stat().st_mtime,
                    }
                    total_size += repo_size
        except Exception as e:
            logger.error(f"Failed to analyze snapshot {snapshot_path}: {e}")

        return {
            "repositories": repositories,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _compare_snapshots(
        self, snapshot1: dict[str, Any], snapshot2: dict[str, Any], show_changes: list[str]
    ) -> dict[str, Any]:
        """Compare two snapshots.

        Args:
            snapshot1: First snapshot analysis
            snapshot2: Second snapshot analysis
            show_changes: Types of changes to show

        Returns:
            Comparison results
        """
        repos1 = set(snapshot1["repositories"].keys())
        repos2 = set(snapshot2["repositories"].keys())

        comparison = {
            "new_repositories": list(repos2 - repos1) if "new_repos" in show_changes else [],
            "deleted_repositories": list(repos1 - repos2) if "deleted_repos" in show_changes else [],
            "common_repositories": list(repos1 & repos2),
            "size_changes": [],
            "modified_repositories": [],
        }

        # Analyze size changes
        if "size_changes" in show_changes:
            for repo_name in comparison["common_repositories"]:
                size1 = snapshot1["repositories"][repo_name]["size_mb"]
                size2 = snapshot2["repositories"][repo_name]["size_mb"]
                size_change = size2 - size1

                if abs(size_change) > 1:  # Only show changes >1MB
                    comparison["size_changes"].append(
                        {
                            "repository": repo_name,
                            "old_size_mb": size1,
                            "new_size_mb": size2,
                            "change_mb": round(size_change, 2),
                        }
                    )

        # Analyze modifications
        if "modified_repos" in show_changes:
            for repo_name in comparison["common_repositories"]:
                mtime1 = snapshot1["repositories"][repo_name]["last_modified"]
                mtime2 = snapshot2["repositories"][repo_name]["last_modified"]

                if mtime2 > mtime1:
                    comparison["modified_repositories"].append(
                        {
                            "repository": repo_name,
                            "last_modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime2)),
                        }
                    )

        return comparison

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

    def _find_restore_matches(self, backup_dir: Path, patterns: list[str]) -> dict[Path, dict[str, Any]]:
        """Find items in backup matching restore patterns.

        Args:
            backup_dir: Backup directory
            patterns: Patterns to match

        Returns:
            Dictionary of matching items
        """
        matches = {}

        for pattern in patterns:
            try:
                for match in backup_dir.rglob(pattern):
                    if match.is_file() or match.is_dir():
                        matches[match] = {
                            "type": "file" if match.is_file() else "directory",
                            "size": match.stat().st_size if match.is_file() else 0,
                            "modified": match.stat().st_mtime,
                        }
            except Exception as e:
                logger.warning(f"Error matching pattern {pattern}: {e}")

        return matches

    def _restore_item(
        self,
        source_path: Path,
        item_info: dict[str, Any],
        target_dir: Path,
        preserve_structure: bool,
        overwrite_existing: bool,
    ) -> dict[str, Any]:
        """Restore a single item.

        Args:
            source_path: Source item path
            item_info: Item information
            target_dir: Target directory
            preserve_structure: Preserve directory structure
            overwrite_existing: Overwrite existing files

        Returns:
            Restore result
        """
        try:
            # Determine target path
            if preserve_structure:
                # Maintain relative path structure
                relative_path = source_path.relative_to(source_path.anchor)
                target_path = target_dir / relative_path
            else:
                # Place directly in target directory
                target_path = target_dir / source_path.name

            # Check for conflicts
            if target_path.exists() and not overwrite_existing:
                return {
                    "source": str(source_path),
                    "target": str(target_path),
                    "status": "conflict",
                    "reason": "Target exists and overwrite_existing=False",
                }

            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy item
            if item_info["type"] == "file":
                import shutil

                shutil.copy2(source_path, target_path)
            else:  # directory
                import shutil

                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(source_path, target_path)

            return {
                "source": str(source_path),
                "target": str(target_path),
                "status": "restored",
                "type": item_info["type"],
                "size_bytes": item_info["size"],
            }

        except Exception as e:
            return {
                "source": str(source_path),
                "target": str(target_path) if "target_path" in locals() else "unknown",
                "status": "failed",
                "error": str(e),
            }

    def _generate_duplicate_report(self, analysis: dict[str, Any], report_path: str) -> None:
        """Generate HTML duplicate code report.

        Args:
            analysis: Duplicate analysis results
            report_path: Path to save report
        """
        # Implementation would generate a detailed HTML report
        # This is a simplified version
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("<html><body><h1>Duplicate Code Analysis Report</h1>")
                f.write(f"<p>Found {len(analysis['duplicates'])} duplicate groups</p>")
                f.write(f"<p>Potential savings: {analysis['statistics']['potential_refactoring_savings']} lines</p>")
                f.write("</body></html>")
            logger.info(f"Duplicate report saved to {report_path}")
        except OSError as e:
            logger.error(f"Failed to save duplicate report: {e}")

    def _generate_snapshot_report(self, comparison: dict[str, Any], report_path: str) -> None:
        """Generate HTML snapshot comparison report.

        Args:
            comparison: Snapshot comparison results
            report_path: Path to save report
        """
        # Implementation would generate a detailed HTML report
        # This is a simplified version
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("<html><body><h1>Workspace Snapshot Comparison</h1>")
                f.write(f"<p>New repositories: {len(comparison['comparison']['new_repositories'])}</p>")
                f.write(f"<p>Deleted repositories: {len(comparison['comparison']['deleted_repositories'])}</p>")
                f.write("</body></html>")
            logger.info(f"Snapshot report saved to {report_path}")
        except OSError as e:
            logger.error(f"Failed to save snapshot report: {e}")
