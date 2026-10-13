"""
Beyond Compare MCP Server

A Model Context Protocol (MCP) server that provides file and directory comparison
capabilities using Beyond Compare. Built with modern MCP 2.11+ standards.
"""

# CRITICAL: Set stdio to binary mode on Windows for Antigravity IDE compatibility
# MUST be done BEFORE any imports that might use stdout
# Antigravity IDE is strict about JSON-RPC protocol and interprets trailing \r as "invalid trailing data"
# Binary mode prevents Python from automatically converting line endings
import os
import sys
import warnings
from typing import Any

if os.name == "nt":  # Windows
    try:
        import msvcrt

        # Set stdin/stdout to binary mode to prevent line ending conversion
        # This fixes "invalid trailing data" errors with Antigravity IDE
        # Use try/except to handle cases where fileno() doesn't exist or isn't callable
        try:
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        except (OSError, AttributeError):
            pass  # stdin might not be a real file descriptor or already patched
        try:
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except (OSError, AttributeError):
            pass  # stdout might not be a real file descriptor or already patched
    except (ImportError, OSError, AttributeError):
        pass  # If msvcrt is not available, continue anyway

# Detect if we're running in stdio mode (MCP server)
_is_stdio_mode = (
    not sys.stdout.isatty()
    or os.getenv("MCP_STDIO_MODE", "").lower() == "true"
    or "stdio" in sys.argv
    or __name__ == "__main__"
)

if _is_stdio_mode:
    # CRITICAL: Patch stdout to prevent ANY writes during initialization
    # This catches print statements, Rich console, FastMCP banners, etc.
    if not hasattr(sys, "_original_stdout"):

        class DevNullStdout:
            """A file-like object that discards all writes (like /dev/null)."""

            def write(self, s: str) -> int:
                # Discard all writes to stdout - they would break JSON-RPC
                return len(s)

            def flush(self) -> None:
                pass

            def isatty(self) -> bool:
                return False

            def readable(self) -> bool:
                return False

            def writable(self) -> bool:
                return True

            def seekable(self) -> bool:
                return False

            @property
            def buffer(self) -> Any:
                import io

                if not hasattr(self, "_bytes"):
                    self._bytes = io.BytesIO()
                return self._bytes

            @property
            def encoding(self) -> str:
                return "utf-8"

            @property
            def errors(self) -> str:
                return "strict"

        # Store original stdout and replace with null device
        # This will be restored before FastMCP.run()
        # Intentional stdio-mode stash on the sys module (restored before run()).
        sys._original_stdout = sys.stdout  # type: ignore[attr-defined]
        sys.stdout = DevNullStdout()

    # Suppress deprecation warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # Configure Python's logging module to prevent stdout pollution
    # FastMCP uses Python's logging module internally
    import logging

    logging.basicConfig(
        level=logging.CRITICAL,  # Only show CRITICAL (suppress everything else)
        format="%(message)s",
        stream=sys.stderr,  # Send to stderr, not stdout
        force=True,  # Override any existing configuration
    )

    # Suppress ALL loggers to prevent any output
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    root_logger.handlers = []

    # Suppress FastMCP and other noisy loggers completely
    for logger_name in [
        "fastmcp",
        "mcp",
        "httpx",
        "httpcore",
        "h11",
        "uvicorn",
        "asyncio",
    ]:
        log = logging.getLogger(logger_name)
        log.setLevel(logging.CRITICAL)
        log.handlers = []
        log.propagate = False
else:
    import logging

import asyncio
import platform
import shutil
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastmcp import FastMCP
from fastmcp.server import create_proxy

from .config import settings
from .exceptions import (
    BeyondCompareCommandError,
    BeyondCompareNotInstalledError,
    BeyondCompareScriptError,
    BeyondCompareTimeoutError,
)
from .multimedia_scanner import MultimediaDriveScanner
from .tools.developer import (
    CodeDuplicateDetector,
    DevRepositoryBackup,
    RepositoryHealthChecker,
    WorkspaceAnalyzer,
)

logger = logging.getLogger(__name__)

# ── MCP tool annotations (fleet TOOL_DESIGN_STANDARDS §9: real MCP hint keys) ──
_READONLY = {"readOnlyHint": True, "openWorldHint": True}
_LOCAL_READONLY = {"readOnlyHint": True, "openWorldHint": False}
_MUTATING = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}
_DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}


def _error_response(message: str, error: Exception | str | None = None, **extra: Any) -> dict[str, Any]:
    """Build a dialogic error payload and log the traceback (TOOL_DESIGN_STANDARDS §7.1 Pattern 3)."""
    logger.exception(message)
    return {"success": False, "message": message, "error": str(error) if error else message, **extra}


class BeyondCompareMCP:
    """Beyond Compare MCP server implementation (FastMCP 3.x unified gateway)."""

    def __init__(
        self,
        bc_path: str | None = None,
        scripts_dir: str | None = None,
        mcp: FastMCP | None = None,
    ):
        """Initialize the Beyond Compare MCP server.

        Args:
            bc_path: Path to Beyond Compare executable
            scripts_dir: Directory for temporary script files
            mcp: Optional FastMCP instance (e.g. from FastMCP.from_fastapi); if omitted, a standalone instance is created
        """
        self.bc_path = self._find_bc_executable(bc_path)
        self.scripts_dir = Path(scripts_dir or settings.BC_SCRIPTS_DIR)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

        # Initialize multimedia scanner
        self.multimedia_scanner = MultimediaDriveScanner()

        # Initialize developer tools
        self.dev_backup = DevRepositoryBackup(self.bc_path)
        self.workspace_analyzer = WorkspaceAnalyzer(self.bc_path)
        self.health_checker = RepositoryHealthChecker(self.bc_path)
        self.duplicate_detector = CodeDuplicateDetector(self.bc_path)

        self.mcp = mcp if mcp is not None else FastMCP(name="Beyond Compare MCP")

        # ── MCP Bridge (ProxyProvider) ────────────────────────────────────────────
        _bridge_proxies: list[str] = []
        bridge_urls = os.getenv("MCP_BRIDGE_URLS", "")
        if bridge_urls:
            for url in bridge_urls.split(","):
                url = url.strip()
                if url:
                    try:
                        self.mcp.add_provider(create_proxy(url))
                        _bridge_proxies.append(url)
                    except Exception as e:
                        logger.warning(f"Skipping unreachable MCP bridge {url}: {e}")

        # Register MCP tools
        self._register_tools()

    def _find_bc_executable(self, bc_path: str | None = None) -> Path:
        """Find the Beyond Compare executable."""
        # If a full path is provided (not just the executable name), verify it exists
        if bc_path and (Path(bc_path).is_absolute() or "/" in bc_path or "\\" in bc_path):
            path = Path(bc_path).expanduser().resolve()
            if path.exists():
                return path
            raise BeyondCompareNotInstalledError(str(path))

        # Check common installation paths first
        if platform.system() == "Windows":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            common_paths = [
                Path(program_files) / "Beyond Compare 5" / "BCompare.exe",
                Path(program_files) / "Beyond Compare 4" / "BCompare.exe",
                Path(program_files) / "Beyond Compare 3" / "BCompare.exe",
                Path(program_files) / "Beyond Compare" / "BCompare.exe",
                Path("C:\\Program Files (x86)\\Beyond Compare 5\\BCompare.exe"),
                Path("C:\\Program Files (x86)\\Beyond Compare 4\\BCompare.exe"),
                Path("C:\\Program Files (x86)\\Beyond Compare 3\\BCompare.exe"),
            ]

            for path in common_paths:
                if path.exists():
                    return path

        # Check PATH for the executable name (provided or default)
        bc_exe = bc_path if bc_path else ("BCompare.exe" if platform.system() == "Windows" else "bcompare")
        which_bc = shutil.which(bc_exe)
        if which_bc:
            return Path(which_bc)

        # If we still haven't found it and a specific executable name was provided, also try the default
        if bc_path and bc_path != ("BCompare.exe" if platform.system() == "Windows" else "bcompare"):
            default_exe = "BCompare.exe" if platform.system() == "Windows" else "bcompare"
            which_default = shutil.which(default_exe)
            if which_default:
                return Path(which_default)

        raise BeyondCompareNotInstalledError(
            f"Beyond Compare not found. Searched for: {bc_exe if bc_path else 'BCompare.exe'}"
        )

    def _register_tools(self) -> None:
        """Register MCP tools with FastMCP."""

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def compare_files(
            left_path: str,
            right_path: str,
            output_report: str | None = None,
        ) -> dict[str, Any]:
            """Compare two files using Beyond Compare.

            Performs a side-by-side comparison of two files using Beyond Compare's
            powerful comparison engine. Supports text, binary, and image files with
            automatic format detection. The comparison uses quick compare mode (size
            and timestamp) for fast results, but can generate detailed reports when
            requested.

            Prerequisites:
                - Beyond Compare must be installed and accessible
                - Both file paths must be valid and accessible
                - Files must exist (will return error if missing)

            Parameters:
                left_path: Path to the left file for comparison
                    - Required: Yes
                    - Can be absolute or relative path
                    - Supports Windows, macOS, and Linux path formats
                    - Example: 'C:/folder/file1.txt' or './file1.txt'

                right_path: Path to the right file for comparison
                    - Required: Yes
                    - Can be absolute or relative path
                    - Must be same file type as left_path for meaningful comparison
                    - Example: 'C:/folder/file2.txt' or './file2.txt'

                output_report: Optional path to save detailed comparison report (default: None)
                    - Optional: Yes
                    - If provided, generates text report with differences
                    - Parent directory will be created if it doesn't exist
                    - Example: 'C:/reports/comparison.txt'

            ## Return Format
                Dictionary containing:
                    - success: Boolean indicating if comparison completed successfully
                    - left_path: Resolved absolute path to left file
                    - right_path: Resolved absolute path to right file
                    - identical: Boolean indicating if files are identical (True if no differences)
                    - differences_found: Boolean indicating if differences were detected
                    - output_report: Path to report file if generated (None otherwise)
                    - message: Human-readable status message
                    - error: Error message string (only present if success is False)

            Usage:
                Use this tool to compare two files and determine if they are identical
                or identify differences between them. Ideal for verifying file integrity,
                checking if backups are current, or validating that files match expected
                versions. The quick compare mode uses file size and modification time
                for fast comparison, making it suitable for large files.

                Common scenarios:
                - Verify backup files match originals
                - Check if configuration files have changed
                - Compare different versions of the same file
                - Validate file integrity after transfer
                - Generate difference reports for documentation

                Best practices:
                - Use absolute paths for reliability
                - Generate reports for important comparisons
                - Check success field before using results
                - Use compare_folders for directory-level comparisons

            ## Examples
                Basic file comparison:
                    result = compare_files(
                        left_path='C:/source/config.txt',
                        right_path='C:/backup/config.txt'
                    )
                    # Returns: {
                    #     'success': True,
                    #     'identical': False,
                    #     'differences_found': True,
                    #     'message': 'Differences found between files'
                    # }

                Compare with report generation:
                    result = compare_files(
                        left_path='C:/docs/manual_v1.txt',
                        right_path='C:/docs/manual_v2.txt',
                        output_report='C:/reports/manual_diff.txt'
                    )
                    # Returns: {
                    #     'success': True,
                    #     'identical': False,
                    #     'output_report': 'C:/reports/manual_diff.txt',
                    #     'message': 'Differences found between files'
                    # }

                Error handling - missing file:
                    result = compare_files(
                        left_path='C:/missing.txt',
                        right_path='C:/exists.txt'
                    )
                    # Returns: {
                    #     'success': False,
                    #     'error': 'Left file not found: C:/missing.txt'
                    # }

            Notes:
                - Comparison uses Beyond Compare's quick compare mode (/qc) for speed
                - Large files may take longer to compare
                - Binary files are compared byte-by-byte
                - Text files support encoding detection
                - Report generation adds overhead but provides detailed differences
                - Paths are validated and resolved before comparison
                - Command injection protection is applied to all paths

            See Also:
                - compare_folders: For comparing entire directory structures
                - sync_folders: For synchronizing folders based on differences
            """
            return self._compare_files(left_path, right_path, output_report)

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def compare_folders(
            left_path: str,
            right_path: str,
            output_report: str | None = None,
            include_subfolders: bool = True,
        ) -> dict[str, Any]:
            """Compare two folders using Beyond Compare.

            Performs a comprehensive comparison of two directory structures, identifying
            files that exist in one folder but not the other, files that differ between
            folders, and files that are identical. Supports recursive subfolder comparison
            and can generate detailed reports showing all differences. This is ideal for
            verifying backups, checking synchronization status, or identifying changes
            between directory versions.

            Prerequisites:
                - Beyond Compare must be installed and accessible
                - Both folder paths must be valid and accessible
                - Folders must exist (will return error if missing)
                - Sufficient permissions to read both directories

            Parameters:
                left_path: Path to the left folder for comparison
                    - Required: Yes
                    - Can be absolute or relative path
                    - Supports Windows, macOS, and Linux path formats
                    - Example: 'C:/source/project' or './project'

                right_path: Path to the right folder for comparison
                    - Required: Yes
                    - Can be absolute or relative path
                    - Should be similar structure to left_path for meaningful comparison
                    - Example: 'C:/backup/project' or './project_backup'

                output_report: Optional path to save detailed comparison report (default: None)
                    - Optional: Yes
                    - If provided, generates summary report with all differences
                    - Report includes file counts, size differences, and mismatch details
                    - Parent directory will be created if it doesn't exist
                    - Example: 'C:/reports/folder_comparison.txt'

                include_subfolders: Whether to recursively compare subfolders (default: True)
                    - Optional: Yes (default: True)
                    - True: Compares all nested directories recursively
                    - False: Only compares files in the top-level directory
                    - Set to False for faster comparison of shallow directory structures

            ## Return Format
                Dictionary containing:
                    - success: Boolean indicating if comparison completed successfully
                    - left_path: Resolved absolute path to left folder
                    - right_path: Resolved absolute path to right folder
                    - include_subfolders: Whether subfolders were included in comparison
                    - differences_found: Boolean indicating if any differences were detected
                    - output_report: Path to report file if generated (None otherwise)
                    - message: Human-readable status message
                    - error: Error message string (only present if success is False)

            Usage:
                Use this tool to compare two directory structures and identify differences
                between them. Perfect for verifying that backups are complete, checking
                synchronization status, identifying missing or changed files, or preparing
                for folder synchronization operations. The recursive comparison option
                allows you to control whether nested directories are included.

                Common scenarios:
                - Verify backup completeness and accuracy
                - Check if folders are synchronized
                - Identify files that have changed between versions
                - Find files that exist in one location but not another
                - Generate reports for documentation or auditing
                - Prepare for folder synchronization operations

                Best practices:
                - Use absolute paths for reliability
                - Generate reports for important comparisons
                - Set include_subfolders=False for shallow directories to save time
                - Review report before performing synchronization
                - Use compare_files for single file comparisons

            ## Examples
                Basic folder comparison:
                    result = compare_folders(
                        left_path='C:/source/project',
                        right_path='C:/backup/project'
                    )
                    # Returns: {
                    #     'success': True,
                    #     'differences_found': True,
                    #     'include_subfolders': True,
                    #     'message': 'Differences found between folders'
                    # }

                Compare top-level only (faster):
                    result = compare_folders(
                        left_path='C:/docs',
                        right_path='D:/docs_backup',
                        include_subfolders=False
                    )
                    # Returns: {
                    #     'success': True,
                    #     'differences_found': False,
                    #     'include_subfolders': False,
                    #     'message': 'Folders are identical'
                    # }

                Compare with detailed report:
                    result = compare_folders(
                        left_path='C:/project_v1',
                        right_path='C:/project_v2',
                        output_report='C:/reports/version_diff.txt'
                    )
                    # Returns: {
                    #     'success': True,
                    #     'differences_found': True,
                    #     'output_report': 'C:/reports/version_diff.txt',
                    #     'message': 'Differences found between folders'
                    # }

                Error handling - missing folder:
                    result = compare_folders(
                        left_path='C:/nonexistent',
                        right_path='C:/exists'
                    )
                    # Returns: {
                    #     'success': False,
                    #     'error': 'Left folder not found: C:/nonexistent'
                    # }

            Notes:
                - Comparison uses Beyond Compare's folder comparison engine
                - Large directories may take significant time to compare
                - Recursive comparison (include_subfolders=True) processes all nested folders
                - Report generation includes summary statistics and file-level differences
                - Paths are validated and resolved before comparison
                - Command injection protection is applied to all paths
                - Comparison results are based on file size and modification time by default

            See Also:
                - compare_files: For comparing individual files
                - sync_folders: For synchronizing folders based on comparison results
            """
            return self._compare_folders(left_path, right_path, output_report, include_subfolders)

        @self.mcp.tool(annotations=_DESTRUCTIVE, output_schema={"type": "object"})
        def sync_folders(
            source_path: str,
            target_path: str,
            sync_mode: str = "mirror",
            dry_run: bool = True,
        ) -> dict[str, Any]:
            """Synchronize folders using Beyond Compare.

            Synchronizes two folders using Beyond Compare's powerful synchronization
            engine. Supports three synchronization modes: mirror (exact copy), update
            (one-way sync), and backup (preserve existing). Includes a dry-run mode
            to preview changes before executing, making it safe to test synchronization
            operations. This tool is ideal for maintaining backups, keeping folders
            in sync, or preparing for deployment.

            Prerequisites:
                - Beyond Compare must be installed and accessible
                - Source folder must exist and be readable
                - Target folder will be created if it doesn't exist
                - Sufficient permissions to read source and write to target
                - Always use dry_run=True first to preview changes

            Parameters:
                source_path: Source directory path (left side, source of truth)
                    - Required: Yes
                    - Can be absolute or relative path
                    - This is the folder that will be copied FROM
                    - Example: 'C:/source/project' or './project'

                target_path: Target directory path (right side, destination)
                    - Required: Yes
                    - Can be absolute or relative path
                    - This is the folder that will be synchronized TO
                    - Will be created if it doesn't exist
                    - Example: 'C:/backup/project' or './project_backup'

                sync_mode: Synchronization mode (default: 'mirror')
                    - Optional: Yes (default: 'mirror')
                    - Valid values: 'mirror', 'update', 'backup'
                    - 'mirror': Exact copy - target matches source exactly (deletes extra files)
                    - 'update': One-way sync - copies new/changed files, preserves target-only files
                    - 'backup': Preserve existing - only copies files that don't exist in target
                    - Example: 'mirror' for exact backups, 'update' for incremental sync

                dry_run: Preview mode - show what would be done without executing (default: True)
                    - Optional: Yes (default: True)
                    - True: Preview changes only, no files are modified
                    - False: Actually perform the synchronization
                    - ALWAYS use True first to review changes before executing
                    - Example: Set to False only after reviewing dry_run results

            ## Return Format
                Dictionary containing:
                    - success: Boolean indicating if synchronization completed successfully
                    - source_path: Resolved absolute path to source folder
                    - target_path: Resolved absolute path to target folder
                    - sync_mode: The synchronization mode used
                    - dry_run: Whether this was a preview (True) or actual sync (False)
                    - changes_detected: Boolean indicating if any differences were found
                    - message: Human-readable status message
                    - error: Error message string (only present if success is False)

            Usage:
                Use this tool to synchronize two folders, keeping them in sync or
                creating backups. The dry-run mode allows you to preview all changes
                before executing, making it safe to test synchronization operations.
                Choose the appropriate sync mode based on your needs: mirror for exact
                copies, update for incremental sync, or backup for preserving existing files.

                Common scenarios:
                - Create exact backups of important folders (mirror mode)
                - Keep development and production folders synchronized (update mode)
                - Incrementally backup files without overwriting (backup mode)
                - Preview synchronization changes before executing
                - Maintain multiple copies of the same folder structure
                - Prepare folders for deployment or distribution

                Best practices:
                - ALWAYS use dry_run=True first to preview changes
                - Review dry_run results carefully before executing
                - Use mirror mode for exact backups where target should match source
                - Use update mode when you want to preserve files that only exist in target
                - Use backup mode to avoid overwriting existing files
                - Verify source_path is correct before synchronizing
                - Keep backups of important data before synchronizing

            ## Examples
                Preview synchronization (dry run):
                    result = sync_folders(
                        source_path='C:/source/project',
                        target_path='C:/backup/project',
                        sync_mode='mirror',
                        dry_run=True
                    )
                    # Returns: {
                    #     'success': True,
                    #     'dry_run': True,
                    #     'changes_detected': True,
                    #     'message': 'Synchronization preview completed successfully'
                    # }

                Execute mirror synchronization:
                    result = sync_folders(
                        source_path='C:/source/project',
                        target_path='C:/backup/project',
                        sync_mode='mirror',
                        dry_run=False
                    )
                    # Returns: {
                    #     'success': True,
                    #     'dry_run': False,
                    #     'changes_detected': True,
                    #     'message': 'Synchronization completed successfully'
                    # }

                Update mode (preserve target-only files):
                    result = sync_folders(
                        source_path='D:/projects/project',
                        target_path='D:/projects/project-backup',
                        sync_mode='update',
                        dry_run=True
                    )
                    # Returns: Preview of update synchronization

                Error handling - missing source:
                    result = sync_folders(
                        source_path='C:/nonexistent',
                        target_path='C:/backup'
                    )
                    # Returns: {
                    #     'success': False,
                    #     'error': 'Source folder not found: C:/nonexistent'
                    # }

            Notes:
                - Synchronization uses Beyond Compare's sync engine for reliability
                - Mirror mode will DELETE files in target that don't exist in source
                - Update mode preserves files that only exist in target
                - Backup mode never overwrites existing files in target
                - Dry-run mode is safe and recommended before actual synchronization
                - Large folders may take significant time to synchronize
                - Paths are validated and resolved before synchronization
                - Command injection protection is applied to all paths
                - Target folder is created automatically if it doesn't exist

            See Also:
                - compare_folders: For comparing folders without synchronizing
                - compare_files: For comparing individual files
            """
            return self._sync_folders(source_path, target_path, sync_mode, dry_run)

        # Multimedia Drive Scanner Tools

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def multimedia_drive_scanner(
            drives: list[str] | None = None,
            recent_days: int | None = None,
            file_types: list[str] | None = None,
        ) -> dict[str, Any]:
            """Scan multimedia drives for complete inventory of media files.

            Scans specified multimedia drives (E:, F:, K:, L:) to create a comprehensive
            inventory of all media files including videos, audio, images, and documents.
            Provides detailed statistics, file counts, sizes, and organization information.
            Supports filtering by file type and modification date to focus on specific
            subsets of the collection. Results are cached for use with duplicate detection.

            Prerequisites:
                - Multimedia drives must be accessible (E:, F:, K:, L:)
                - Drives must contain 'multimedia files' folder structure
                - Sufficient permissions to read drive contents
                - Drives must be mounted and available

            Parameters:
                drives: Specific drives to scan (default: None - scans all available)
                    - Optional: Yes (default: None - all available drives)
                    - List of drive letters to scan (e.g., ['E:', 'F:'])
                    - If None, automatically detects and scans all available drives
                    - Only scans drives that contain 'multimedia files' folder
                    - Example: ['E:', 'F:'] to scan only E: and F: drives

                recent_days: Only include files modified in last N days (default: None)
                    - Optional: Yes (default: None - all files)
                    - Integer number of days to look back
                    - Filters files by modification date
                    - Useful for finding recently added or changed files
                    - Example: 30 to find files modified in last 30 days

                file_types: Filter by media types (default: None - all types)
                    - Optional: Yes (default: None - all media types)
                    - List of media type strings: 'video', 'audio', 'images', 'documents'
                    - Filters scan results to only specified types
                    - Can specify multiple types: ['video', 'audio']
                    - Example: ['video'] to scan only video files

            ## Return Format
                Dictionary containing:
                    - success: Boolean indicating if scan completed successfully
                    - scan_time_seconds: Time taken to complete scan
                    - drives_scanned: List of drive letters that were scanned
                    - total_files: Total number of files found across all drives
                    - total_size_gb: Total size of all files in gigabytes
                    - results: Dictionary with per-drive scan results
                        - Each drive contains: files, file_count, total_size_gb, media_stats
                    - scan_filters: Dictionary showing filters applied
                    - summary: Summary statistics including media distribution
                    - error: Error message string (only present if success is False)

            Usage:
                Use this tool to inventory multimedia files across multiple drives,
                providing a comprehensive view of your media collection. Ideal for
                understanding collection size, organization, and identifying files
                for management or cleanup. Results are cached for use with duplicate
                detection tools.

                Common scenarios:
                - Get complete inventory of multimedia collection
                - Find recently added files (use recent_days filter)
                - Analyze collection by media type (use file_types filter)
                - Prepare for duplicate detection (scan results are cached)
                - Monitor drive space usage and organization
                - Generate reports on media collection statistics

                Best scenarios:
                - Scan all drives first to get complete picture
                - Use file_types filter to focus on specific media types
                - Use recent_days to find recently added content
                - Review summary statistics for collection overview
                - Use cached results with find_multimedia_duplicates

            ## Examples
                Scan all available drives:
                    result = multimedia_drive_scanner()
                    # Returns: {
                    #     'success': True,
                    #     'total_files': 15234,
                    #     'total_size_gb': 1234.56,
                    #     'drives_scanned': ['E:', 'F:', 'K:', 'L:']
                    # }

                Scan specific drives for videos only:
                    result = multimedia_drive_scanner(
                        drives=['E:', 'F:'],
                        file_types=['video']
                    )
                    # Returns: Video files from E: and F: drives only

                Find recently added files:
                    result = multimedia_drive_scanner(
                        recent_days=7,
                        file_types=['video', 'audio']
                    )
                    # Returns: Video and audio files modified in last 7 days

                Error handling - no drives found:
                    result = multimedia_drive_scanner()
                    # Returns: {
                    #     'success': False,
                    #     'error': 'No multimedia drives found'
                    # }

            Notes:
                - Scan results are cached for use with duplicate detection
                - Only scans drives containing 'multimedia files' folder
                - Large collections may take several minutes to scan
                - File size minimum is 1KB (tiny files are excluded)
                - Media types are determined by file extension
                - Scan time increases with number of files and drives
                - Results include detailed per-drive statistics

            See Also:
                - find_multimedia_duplicates: For finding duplicate files (uses scan cache)
                - detect_usb_drives: For detecting USB drives for sync operations
            """
            return self.multimedia_scanner.scan_multimedia_drives(
                drives=drives, recent_days=recent_days, file_types=file_types
            )

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def find_multimedia_duplicates(
            drives: list[str] | None = None,
            min_size_mb: float = 0.1,
            file_types: list[str] | None = None,
            use_content_hash: bool = True,
        ) -> dict[str, Any]:
            """Find duplicate multimedia files across drives.

            Identifies duplicate multimedia files across specified drives using either
            content hash (accurate but slower) or name/size matching (faster but less
            accurate). Groups duplicates together and provides recommendations for which
            files to keep and which to remove, along with potential space savings.
            Uses cached scan results from multimedia_drive_scanner when available.

            Prerequisites:
                - Multimedia drives must be accessible
                - Should run multimedia_drive_scanner first for best results
                - Sufficient disk space for hash calculation (if use_content_hash=True)
                - Files must be readable for hash calculation

            Parameters:
                drives: Specific drives to check (default: None - uses last scan results)
                    - Optional: Yes (default: None - uses cached scan results)
                    - List of drive letters to check (e.g., ['E:', 'F:'])
                    - If None, uses results from last multimedia_drive_scanner call
                    - If specified, performs new scan before duplicate detection
                    - Example: ['E:', 'F:'] to check only E: and F: drives

                min_size_mb: Minimum file size in MB to check for duplicates (default: 0.1)
                    - Optional: Yes (default: 0.1 MB)
                    - Files smaller than this are excluded from duplicate detection
                    - Reduces processing time by skipping tiny files
                    - Recommended: 1.0 MB or higher for faster processing
                    - Example: 10.0 to only check files larger than 10 MB

                file_types: Filter by media types (default: None - all types)
                    - Optional: Yes (default: None - all media types)
                    - List of media type strings: 'video', 'audio', 'images', 'documents'
                    - Filters duplicate detection to only specified types
                    - Can specify multiple types: ['video', 'audio']
                    - Example: ['video'] to find only duplicate video files

                use_content_hash: Use content hash for accurate detection (default: True)
                    - Optional: Yes (default: True)
                    - True: Uses SHA-256 hash of file content (accurate, slower)
                    - False: Uses filename and size matching (faster, less accurate)
                    - Recommended: True for accurate results, False for quick scan
                    - Hash calculation can be slow for large files
                    - Example: Set to False for initial quick scan, True for final check

            ## Return Format
                Dictionary containing:
                    - success: Boolean indicating if duplicate detection completed successfully
                    - scan_time_seconds: Time taken to complete duplicate detection
                    - detection_method: Method used ('content_hash' or 'name_and_size')
                    - total_files_checked: Total number of files analyzed
                    - duplicate_groups: List of duplicate file groups
                        - Each group contains: files, duplicate_count, potential_savings_mb
                    - total_duplicate_groups: Number of duplicate groups found
                    - total_duplicate_files: Total number of duplicate files (excluding originals)
                    - total_savings_gb: Total potential space savings in gigabytes
                    - recommendations: List of cleanup recommendations
                    - error: Error message string (only present if success is False)

            Usage:
                Use this tool to identify duplicate files across your multimedia collection,
                helping you reclaim disk space by removing unnecessary duplicates. The tool
                groups duplicates together and provides recommendations for which files to
                keep (based on drive priority) and which to remove. Use content hash for
                accurate detection or name/size for faster scanning.

                Common scenarios:
                - Find and remove duplicate files to free up disk space
                - Identify files that exist on multiple drives
                - Get recommendations for which duplicates to keep
                - Calculate potential space savings from cleanup
                - Verify backup completeness (should have duplicates)
                - Organize multimedia collection by removing duplicates

                Best practices:
                - Run multimedia_drive_scanner first to cache results
                - Start with use_content_hash=False for quick initial scan
                - Use use_content_hash=True for final accurate detection
                - Set min_size_mb to 1.0 or higher to skip tiny files
                - Review recommendations before deleting files
                - Start with largest duplicates for maximum space savings

            ## Examples
                Find duplicates using cached scan results:
                    result = find_multimedia_duplicates()
                    # Returns: {
                    #     'success': True,
                    #     'total_duplicate_groups': 42,
                    #     'total_savings_gb': 15.3,
                    #     'duplicate_groups': [...]
                    # }

                Quick scan with name/size matching:
                    result = find_multimedia_duplicates(
                        min_size_mb=10.0,
                        use_content_hash=False
                    )
                    # Returns: Fast duplicate detection using filename and size

                Accurate detection for video files only:
                    result = find_multimedia_duplicates(
                        file_types=['video'],
                        min_size_mb=100.0,
                        use_content_hash=True
                    )
                    # Returns: Accurate duplicate detection for large video files

                Check specific drives:
                    result = find_multimedia_duplicates(
                        drives=['E:', 'F:'],
                        min_size_mb=1.0
                    )
                    # Returns: Duplicates between E: and F: drives

            Notes:
                - Uses cached scan results from multimedia_drive_scanner when available
                - Content hash calculation can be slow for large files
                - Name/size matching is faster but may miss some duplicates
                - Duplicate groups are sorted by potential savings (largest first)
                - Recommendations prioritize keeping files on lower drive letters (E: < F: < K: < L:)
                - Total savings represents space that could be freed by removing duplicates
                - Large collections may take significant time to process

            See Also:
                - multimedia_drive_scanner: For scanning drives before duplicate detection
                - detect_usb_drives: For detecting USB drives for sync operations
            """
            return self.multimedia_scanner.find_multimedia_duplicates(
                drives=drives,
                min_size_mb=min_size_mb,
                file_types=file_types,
                use_content_hash=use_content_hash,
            )

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def detect_usb_drives() -> dict[str, Any]:
            """Detect connected USB drives for sync operations.

            Scans the system for connected USB drives and returns information about
            each drive including drive letter, label, available space, and whether
            it contains a multimedia files folder. Useful for identifying removable
            storage devices that can be used for backup or synchronization operations.
            Automatically excludes the fixed multimedia drives (E:, F:, K:, L:).

            Prerequisites:
                - System must support USB drive detection
                - USB drives must be mounted and accessible
                - On Windows, win32api provides better detection (optional dependency)
                - Drives must be recognized by the operating system

            Parameters:
                None: This tool takes no parameters

            ## Return Format
                Dictionary containing:
                    - success: Boolean indicating if detection completed successfully
                    - usb_drives: List of USB drive information dictionaries
                        - Each drive contains:
                            - drive_letter: Drive letter (e.g., 'G:')
                            - label: Volume label or 'Unknown Label'
                            - space_info: Dictionary with total_gb, used_gb, free_gb, used_percent
                            - multimedia_folder_exists: Boolean indicating if 'multimedia files' folder exists
                            - detection_method: 'win32api' or 'fallback' (optional)
                    - count: Number of USB drives detected
                    - message: Human-readable status message
                    - error: Error message string (only present if success is False)

            Usage:
                Use this tool to identify connected USB drives that can be used for
                backup or synchronization operations. The tool automatically excludes
                the fixed multimedia drives and focuses on removable storage devices.
                Check the multimedia_folder_exists flag to see if drives are ready
                for multimedia sync operations.

                Common scenarios:
                - Find USB drives for backup operations
                - Identify removable storage for synchronization
                - Check available space on USB drives
                - Verify USB drives are ready for multimedia sync
                - Prepare for backup to external storage
                - Monitor connected removable storage devices

                Best practices:
                - Check space_info before starting large sync operations
                - Verify multimedia_folder_exists if using for multimedia sync
                - Use drive label to identify specific USB drives
                - Check free_gb to ensure sufficient space
                - Use with sync_folders for backup operations

            ## Examples
                Detect all USB drives:
                    result = detect_usb_drives()
                    # Returns: {
                    #     'success': True,
                    #     'count': 2,
                    #     'usb_drives': [
                    #         {
                    #             'drive_letter': 'G:',
                    #             'label': 'BACKUP_DRIVE',
                    #             'space_info': {'free_gb': 500.0, 'total_gb': 1000.0},
                    #             'multimedia_folder_exists': True
                    #         }
                    #     ]
                    # }

                Check USB drive space:
                    result = detect_usb_drives()
                    if result['success']:
                        for drive in result['usb_drives']:
                            print(f"{drive['drive_letter']}: {drive['space_info']['free_gb']} GB free")
                    # Output: G: 500.0 GB free

                Error handling - detection failed:
                    result = detect_usb_drives()
                    # Returns: {
                    #     'success': False,
                    #     'error': 'USB drive detection failed - may require win32api dependency'
                    # }

            Notes:
                - Automatically excludes fixed multimedia drives (E:, F:, K:, L:)
                - Uses win32api on Windows for accurate detection (optional dependency)
                - Falls back to directory scanning if win32api not available
                - Only detects drives that are mounted and accessible
                - Drive labels may show as 'Unknown Label' if win32api unavailable
                - Detection method is indicated in drive information when available
                - USB drives must be recognized by operating system

            See Also:
                - multimedia_drive_scanner: For scanning multimedia drives
                - sync_folders: For synchronizing folders to USB drives
                - find_multimedia_duplicates: For finding duplicate files
            """
            try:
                usb_drives = self.multimedia_scanner.get_usb_drives()
                return {
                    "success": True,
                    "usb_drives": usb_drives,
                    "count": len(usb_drives),
                    "message": f"Found {len(usb_drives)} USB drive(s)",
                }
            except Exception as e:
                logger.exception(f"USB drive detection failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": "USB drive detection failed - may require win32api dependency",
                }

        # Developer Backup and Repository Management Tools
        @self.mcp.tool(annotations=_MUTATING, output_schema={"type": "object"})
        def backup_dev_repositories(
            source_path: str,
            backup_path: str,
            exclude_patterns: list[str] | None = None,
            include_git_essentials: bool = True,
            compress: bool = True,
            incremental: bool = True,
            dry_run: bool = False,
        ) -> dict[str, Any]:
            """Smart backup of development repositories with intelligent filtering.

            Copies repo checkouts to a backup location while excluding
            regenerable artifacts (node_modules, __pycache__, dist, .next).
            Optionally preserves git essentials, compresses output, and runs
            incrementally. Preview with dry_run=True before writing.

            ## Return Format
            Dictionary with success, source_path, backup_path, dry_run,
            changes_detected, message, and error (only when success is False).

            ## Examples
            Preview a backup:
                backup_dev_repositories(source_path='D:/Dev/repos',
                    backup_path='E:/backups/repos', dry_run=True)
            Execute an incremental compressed backup:
                backup_dev_repositories(source_path='D:/Dev/repos',
                    backup_path='E:/backups/repos', compress=True,
                    incremental=True, dry_run=False)
            """
            return self.dev_backup.backup_repositories(
                source_path,
                backup_path,
                exclude_patterns,
                include_git_essentials,
                compress,
                incremental,
                dry_run,
            )

        @self.mcp.tool(annotations=_MUTATING, output_schema={"type": "object"})
        def analyze_dev_workspace(
            workspace_path: str,
            report_path: str | None = None,
            include_git_stats: bool = True,
            include_dependencies: bool = True,
            include_size_analysis: bool = True,
        ) -> dict[str, Any]:
            """Analyze development workspace for insights and optimization opportunities.

            Reports language mix, dependency manifests, git statistics, and
            disk usage per checkout. Optionally writes an HTML report.

            ## Return Format
            Dictionary with success, workspace_path, language_stats,
            dependencies, git_stats, size_analysis, report_path, message,
            and error (only when success is False).

            ## Examples
            Full analysis with HTML report:
                analyze_dev_workspace(workspace_path='D:/Dev/repos',
                    report_path='C:/reports/workspace.html')
            Quick analysis without extras:
                analyze_dev_workspace(workspace_path='D:/Dev/repos',
                    include_git_stats=False, include_dependencies=False,
                    include_size_analysis=False)
            """
            return self.workspace_analyzer.analyze_workspace(
                workspace_path,
                report_path,
                include_git_stats,
                include_dependencies,
                include_size_analysis,
            )

        @self.mcp.tool(annotations=_MUTATING, output_schema={"type": "object"})
        def scan_repo_health(
            repos_path: str,
            checks: list[str] | None = None,
            report_path: str | None = None,
            fix_issues: bool = False,
        ) -> dict[str, Any]:
            """Scan repository health and identify potential issues.

            Checks git status, large files, and outdated dependencies across
            every checkout under repos_path. With fix_issues=True applies
            safe automatic fixes; otherwise reports only.

            ## Return Format
            Dictionary with success, repos_path, issues (per-repo list),
            fixed (applied fixes), report_path, message, and error
            (only when success is False).

            ## Examples
            Report-only scan:
                scan_repo_health(repos_path='D:/Dev/repos')
            Scan with automatic fixes:
                scan_repo_health(repos_path='D:/Dev/repos', fix_issues=True)
            """
            return self.health_checker.scan_repository_health(repos_path, checks, report_path, fix_issues)

        @self.mcp.tool(annotations=_DESTRUCTIVE, output_schema={"type": "object"})
        def cleanup_dev_artifacts(
            repos_path: str,
            targets: list[str] | None = None,
            size_threshold_mb: float = 100,
            dry_run: bool = True,
        ) -> dict[str, Any]:
            """Clean up build artifacts and temporary files across repositories.

            Removes regenerable targets (node_modules, __pycache__, .next,
            dist) above size_threshold_mb. ALWAYS preview with dry_run=True
            first — dry_run=False deletes files irreversibly.

            ## Return Format
            Dictionary with success, repos_path, dry_run, removed
            (reclaimed bytes/paths), message, and error (only when
            success is False).

            ## Examples
            Preview reclaimable space:
                cleanup_dev_artifacts(repos_path='D:/Dev/repos', dry_run=True)
            Execute cleanup of large targets only:
                cleanup_dev_artifacts(repos_path='D:/Dev/repos',
                    size_threshold_mb=500, dry_run=False)
            """
            return self.health_checker.cleanup_development_artifacts(repos_path, targets, size_threshold_mb, dry_run)

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def find_duplicate_code(
            repos_path: str,
            file_types: list[str] | None = None,
            min_lines: int = 10,
            similarity_threshold: float = 0.8,
            report_path: str | None = None,
        ) -> dict[str, Any]:
            """Find duplicate code across repositories.

            Detects near-duplicate blocks (>= min_lines) in the given file
            types above similarity_threshold. Optionally writes a report.

            ## Return Format
            Dictionary with success, repos_path, duplicate_groups,
            total_duplicate_files, report_path, message, and error
            (only when success is False).

            ## Examples
            Python duplicates at default sensitivity:
                find_duplicate_code(repos_path='D:/Dev/repos',
                    file_types=['.py'])
            Strict TypeScript scan with report:
                find_duplicate_code(repos_path='D:/Dev/repos',
                    file_types=['.ts', '.tsx'], min_lines=20,
                    similarity_threshold=0.9,
                    report_path='C:/reports/duplicates.txt')
            """
            return self.duplicate_detector.find_duplicate_code(
                repos_path, file_types, min_lines, similarity_threshold, report_path
            )

        @self.mcp.tool(annotations=_READONLY, output_schema={"type": "object"})
        def compare_workspace_snapshots(
            snapshot1_path: str,
            snapshot2_path: str,
            report_path: str | None = None,
            show_changes: list[str] | None = None,
        ) -> dict[str, Any]:
            """Compare workspace snapshots to identify changes over time.

            Diffs two snapshot files (as produced by backup/analysis runs)
            and reports added, removed, and modified repositories.

            ## Return Format
            Dictionary with success, snapshot1_path, snapshot2_path,
            added, removed, modified, report_path, message, and error
            (only when success is False).

            ## Examples
            Compare last two snapshots:
                compare_workspace_snapshots(
                    snapshot1_path='E:/backups/snap-2026-10-01.json',
                    snapshot2_path='E:/backups/snap-2026-10-13.json')
            """
            return self.duplicate_detector.compare_workspace_snapshots(
                snapshot1_path, snapshot2_path, report_path, show_changes
            )

        @self.mcp.tool(annotations=_DESTRUCTIVE, output_schema={"type": "object"})
        def selective_restore(
            backup_path: str,
            restore_items: list[str],
            target_path: str,
            preserve_structure: bool = True,
            overwrite_existing: bool = False,
        ) -> dict[str, Any]:
            """Selectively restore specific projects or files from backup.

            Restores restore_items from backup_path into target_path,
            optionally preserving directory structure. Set
            overwrite_existing=True only after reviewing the item list.

            ## Return Format
            Dictionary with success, backup_path, target_path,
            restored (paths written), message, and error (only when
            success is False).

            ## Examples
            Restore one project without overwriting:
                selective_restore(backup_path='E:/backups/repos',
                    restore_items=['beyondcompare-mcp'],
                    target_path='D:/Dev/repos')
            """
            return self.duplicate_detector.selective_restore(
                backup_path,
                restore_items,
                target_path,
                preserve_structure,
                overwrite_existing,
            )

        @self.mcp.tool(annotations=_LOCAL_READONLY, output_schema={"type": "object"}, app=True)
        async def bc_status() -> dict[str, Any]:
            """Server status: Beyond Compare detection, tool count, uptime.

            Local-only status probe for dashboards and agents. Reports
            whether the Beyond Compare executable was found, how many MCP
            tools are registered, and gateway uptime.

            ## Return Format
            Dictionary with success, detected (Beyond Compare found),
            executable, scripts_dir, tool_count, uptime_s, message.

            ## Examples
            Check the server is healthy:
                bc_status()
                # Returns: {'success': True, 'detected': True,
                #   'tool_count': 18, ...}
            """
            tools = len(_ATOMIC_TOOLS) + len(_AGENTIC_TOOLS)
            exe = Path(self.bc_path)
            return {
                "success": True,
                "detected": exe.exists(),
                "executable": str(self.bc_path),
                "scripts_dir": str(self.scripts_dir),
                "tool_count": tools,
                "message": "Beyond Compare MCP status",
            }

        @self.mcp.tool(annotations=_LOCAL_READONLY, output_schema={"type": "object"})
        def bc_help(topic: str | None = None) -> dict[str, Any]:
            """Usage help for the Beyond Compare MCP tool surface.

            Returns the tool catalog with one-line guidance each, or
            detailed guidance for a single topic (tool name).

            ## Return Format
            Dictionary with success, topic, tools (name -> guidance),
            message.

            ## Examples
            Full catalog:
                bc_help()
            One tool:
                bc_help(topic='sync_folders')
            """
            catalog = {
                "compare_files": "Diff two files; optional output_report. Read-only.",
                "compare_folders": "Diff two trees; include_subfolders=false for shallow. Read-only.",
                "sync_folders": "Mirror/update/backup sync. ALWAYS dry_run=True first. Destructive.",
                "multimedia_drive_scanner": "Inventory media drives E:/F:/K:/L:. Read-only.",
                "find_multimedia_duplicates": "Hash-based duplicate finder over scan cache. Read-only.",
                "detect_usb_drives": "List removable drives for sync targets. Read-only.",
                "backup_dev_repositories": "Filtered repo backup with compress/incremental. Mutating.",
                "analyze_dev_workspace": "Language/deps/git/size analysis + HTML report. Mutating.",
                "scan_repo_health": "Git/large-file/dep checks; fix_issues=True auto-fixes. Mutating.",
                "cleanup_dev_artifacts": "Delete regenerable artifacts. Preview first. Destructive.",
                "find_duplicate_code": "Cross-repo near-duplicate detector. Read-only.",
                "compare_workspace_snapshots": "Diff two snapshots over time. Read-only.",
                "selective_restore": "Restore items from backup. Destructive.",
                "beyondcompare_agentic_workflow": "Natural-language goal via ctx.sample. Agentic.",
                "beyondcompare_sampling_hint": "Query/category hints for sampling hosts. Agentic.",
                "bc_status": "This server's health. Local read-only.",
                "bc_help": "This catalog. Local read-only.",
                "bc_shutdown": "Orderly server shutdown. Destructive.",
            }
            if topic:
                return {
                    "success": topic in catalog,
                    "topic": topic,
                    "tools": {topic: catalog[topic]} if topic in catalog else {},
                    "message": catalog.get(topic, f"Unknown topic: {topic}"),
                }
            return {"success": True, "topic": None, "tools": catalog, "message": "Beyond Compare MCP tool catalog"}

        @self.mcp.tool(annotations=_DESTRUCTIVE, output_schema={"type": "object"})
        def bc_shutdown() -> dict[str, Any]:
            """Shut the MCP server down gracefully (orderly self-termination).

            Responds immediately, then exits the process ~500 ms later so
            in-flight responses and depot writes can flush.

            ## Return Format
            Dictionary with success True and a shutdown message.

            ## Examples
            Restart before upgrades:
                bc_shutdown()
            """
            import threading as _threading

            _threading.Timer(0.5, lambda: os._exit(0)).start()
            return {"success": True, "message": "beyondcompare-mcp shutting down in ~500 ms"}

    def _run_bc_command(
        self,
        args: Sequence[str | Path],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Run a Beyond Compare command with proper input validation.

        Args:
            args: List of command-line arguments (validated)
            timeout: Command timeout in seconds

        Returns:
            Dictionary with command results

        Raises:
            BeyondCompareCommandError: If command fails
            BeyondCompareTimeoutError: If command times out
        """
        if not self.bc_path:
            self.bc_path = self._find_bc_executable()

        # Input validation - only allow safe arguments
        safe_args = []
        for arg in args:
            arg_str = str(arg)
            # Basic path validation to prevent command injection
            if not self._is_safe_argument(arg_str):
                raise BeyondCompareCommandError(
                    command=f"Invalid argument: {arg_str}",
                    returncode=-1,
                    stderr="Invalid or unsafe argument detected",
                )
            safe_args.append(arg_str)

        cmd = [str(self.bc_path), *safe_args]

        try:
            logger.debug(f"Executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout or settings.COMMAND_TIMEOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )

            # Beyond Compare returns:
            # 0 = success, no differences
            # 1 = success, differences found
            # 2+ = error
            if result.returncode >= 2:
                raise BeyondCompareCommandError(
                    command=" ".join(cmd),
                    returncode=result.returncode,
                    stderr=result.stderr,
                )

            return {
                "success": True,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "has_differences": result.returncode == 1,
            }

        except subprocess.TimeoutExpired as e:
            raise BeyondCompareTimeoutError(
                command=" ".join(cmd),
                timeout=timeout or settings.COMMAND_TIMEOUT,
            ) from e

        except Exception as e:
            raise BeyondCompareCommandError(
                command=" ".join(cmd),
                returncode=getattr(e, "returncode", -1),
                stderr=str(e),
            ) from e

    def _is_safe_argument(self, arg: str) -> bool:
        """Validate that an argument is safe to pass to subprocess.

        Args:
            arg: Argument to validate

        Returns:
            True if argument is safe, False otherwise
        """
        # Block common command injection patterns
        dangerous_chars = [";", "|", "&", ">", "<", "`", "$", "(", ")"]
        for char in dangerous_chars:
            if char in arg:
                return False

        # Allow normal paths and Beyond Compare arguments
        return True

    def _validate_path(self, path_str: str) -> Path:
        """Validate and resolve a path safely.

        Args:
            path_str: Path string to validate

        Returns:
            Validated Path object

        Raises:
            ValueError: If path is invalid or unsafe
        """
        try:
            path = Path(path_str).expanduser().resolve()

            # Prevent path traversal attacks
            if ".." in path_str:
                raise ValueError("Path traversal detected")

            return path
        except Exception as e:
            raise ValueError(f"Invalid path: {path_str}") from e

    def _create_script(self, commands: list[str], script_name: str) -> Path:
        """Create a temporary Beyond Compare script file.

        Args:
            commands: List of Beyond Compare script commands
            script_name: Base name for the script file

        Returns:
            Path to the created script file

        Raises:
            BeyondCompareScriptError: If script creation fails
        """
        try:
            self.scripts_dir.mkdir(parents=True, exist_ok=True)

            # Create a unique script filename using tempfile for security
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".bcscript",
                dir=self.scripts_dir,
                delete=False,
                encoding="utf-8",
            ) as script_file:
                # Write the script with proper line endings
                script_content = "\r\n".join(commands) + "\r\n"
                script_file.write(script_content)
                script_path = Path(script_file.name)

            return script_path

        except Exception as e:
            raise BeyondCompareScriptError(
                script_path="unknown",
                error=str(e),
            ) from e

    def _compare_files(
        self,
        left_path: str,
        right_path: str,
        output_report: str | None = None,
    ) -> dict[str, Any]:
        """Compare two files using Beyond Compare."""
        try:
            # Validate and resolve paths
            left = self._validate_path(left_path)
            right = self._validate_path(right_path)

            if not left.exists():
                return {
                    "success": False,
                    "error": f"Left file not found: {left_path}",
                    "left_path": left_path,
                    "right_path": right_path,
                }
            if not right.exists():
                return {
                    "success": False,
                    "error": f"Right file not found: {right_path}",
                    "left_path": left_path,
                    "right_path": right_path,
                }

            # Build command arguments for silent comparison
            # Beyond Compare 5 requires /qc (Quick Compare) for command-line operation
            args = ["/silent", "/qc", str(left), str(right)]

            # Add report generation if requested
            if output_report:
                report_path = self._validate_path(output_report)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                args.extend(["/qc=text-conflicts", f"/o={report_path}"])

            # Run the comparison
            result = self._run_bc_command(args)

            return {
                "success": True,
                "left_path": str(left),
                "right_path": str(right),
                "identical": not result["has_differences"],
                "differences_found": result["has_differences"],
                "output_report": output_report,
                "message": (
                    "Files are identical" if not result["has_differences"] else "Differences found between files"
                ),
            }

        except Exception as e:
            logger.exception(f"File comparison failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "left_path": left_path,
                "right_path": right_path,
                "message": f"Comparison failed: {e}",
            }

    @staticmethod
    def _parse_folder_summary(report_path: str) -> tuple[bool, dict[str, int] | None]:
        """Verdict from a folder-report summary: orphan/different counts.

        Returns (differences_found, counts) or (False, None) when unreadable.
        """
        import re as _re

        try:
            text = Path(report_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False, None
        counts = {"left_orphans": 0, "right_orphans": 0, "different": 0}
        patterns = {
            "left_orphans": r"Left Orphan Files \((\d+)\)",
            "right_orphans": r"Right Orphan Files \((\d+)\)",
            "different": r"Different Files \((\d+)\)",
        }
        found_any = False
        for key, pattern in patterns.items():
            m = _re.search(pattern, text)
            if m:
                found_any = True
                counts[key] = int(m.group(1))
        if not found_any:
            return False, None
        return any(v > 0 for v in counts.values()), counts

    def _compare_folders(
        self,
        left_path: str,
        right_path: str,
        output_report: str | None = None,
        include_subfolders: bool = True,
    ) -> dict[str, Any]:
        """Compare two folders using Beyond Compare."""
        try:
            # Validate and resolve paths
            left = self._validate_path(left_path)
            right = self._validate_path(right_path)

            if not left.exists():
                return {
                    "success": False,
                    "error": f"Left folder not found: {left_path}",
                    "left_path": left_path,
                    "right_path": right_path,
                }
            if not right.exists():
                return {
                    "success": False,
                    "error": f"Right folder not found: {right_path}",
                    "left_path": left_path,
                    "right_path": right_path,
                }

            # Create script for folder comparison
            script_commands = [
                f'load "{left}" "{right}"',
                "expand all" if include_subfolders else "",
                "select all.files",
            ]

            # Always generate a summary report: BC5 script exit codes do NOT
            # distinguish identical vs different (rc is 0 either way), so the
            # verdict comes from parsing the orphan/different counts below.
            # (Also: there is no "script-exit" command in BC5 — it fatals with
            # rc 106. Scripts simply end at EOF.)
            import tempfile as _tempfile

            if output_report:
                report_path = self._validate_path(output_report)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_target = str(report_path)
                _temp_report = None
            else:
                _tmp = _tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="folder_compare_", delete=False)
                _tmp.close()
                report_target = _tmp.name
                _temp_report = report_target
            script_commands.append(
                f'folder-report layout:summary options:display-mismatches output-to:"{report_target}"'
            )

            # Create and run script
            script_path = self._create_script(script_commands, "folder_compare")
            try:
                result = self._run_bc_command([f"@{script_path!s}"])
                differences_found, counts = self._parse_folder_summary(report_target)
                if counts is None:
                    # Report unreadable — fall back to exit-code heuristic.
                    differences_found = result["has_differences"]
            finally:
                # Clean up script file
                try:
                    script_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up script file {script_path}: {e}")
                if _temp_report:
                    try:
                        Path(_temp_report).unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temp report {_temp_report}: {e}")

            if counts is None:
                counts = {"left_orphans": 0, "right_orphans": 0, "different": 0}
            return {
                "success": True,
                "left_path": str(left),
                "right_path": str(right),
                "include_subfolders": include_subfolders,
                "differences_found": differences_found,
                "left_orphans": counts["left_orphans"],
                "right_orphans": counts["right_orphans"],
                "different_files": counts["different"],
                "output_report": output_report,
                "message": ("Folders are identical" if not differences_found else "Differences found between folders"),
            }

        except Exception as e:
            logger.exception(f"Folder comparison failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "left_path": left_path,
                "right_path": right_path,
                "message": f"Comparison failed: {e}",
            }

    def _sync_folders(
        self,
        source_path: str,
        target_path: str,
        sync_mode: str = "mirror",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Synchronize folders using Beyond Compare."""
        try:
            # Validate sync mode
            valid_modes = ["mirror", "update", "backup"]
            if sync_mode not in valid_modes:
                return {
                    "success": False,
                    "error": f"Invalid sync mode. Must be one of: {', '.join(valid_modes)}",
                    "source_path": source_path,
                    "target_path": target_path,
                    "sync_mode": sync_mode,
                }

            # Validate and resolve paths
            source = self._validate_path(source_path)
            target = self._validate_path(target_path)

            if not source.exists():
                return {
                    "success": False,
                    "error": f"Source folder not found: {source_path}",
                    "source_path": source_path,
                    "target_path": target_path,
                    "sync_mode": sync_mode,
                }

            # Create target directory if it doesn't exist
            target.mkdir(parents=True, exist_ok=True)

            # Build script commands based on sync mode
            script_commands = [
                f'load "{source}" "{target}"',
                "expand all",
                "select all.files all.folders",
            ]

            # Add sync command based on mode
            if sync_mode == "mirror":
                script_commands.append("sync mirror:left->right")
            elif sync_mode == "update":
                script_commands.append("sync update:left->right")
            elif sync_mode == "backup":
                script_commands.append("sync create:left->right")

            # Add dry run option
            if dry_run:
                script_commands[-1] += " preview"

            # NOTE: no "script-exit" — unknown command in BC5 (fatals rc 106).
            # Scripts end at EOF.

            # Create and run script
            script_path = self._create_script(script_commands, f"sync_{sync_mode}")
            try:
                result = self._run_bc_command([f"@{script_path!s}"])
            finally:
                # Clean up script file
                try:
                    script_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up script file {script_path}: {e}")

            return {
                "success": True,
                "source_path": str(source),
                "target_path": str(target),
                "sync_mode": sync_mode,
                "dry_run": dry_run,
                "changes_detected": result["has_differences"],
                "message": (f"Synchronization {'preview' if dry_run else 'completed'} successfully"),
            }

        except Exception as e:
            logger.error(f"Folder synchronization failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "source_path": source_path,
                "target_path": target_path,
                "sync_mode": sync_mode,
                "message": f"Synchronization failed: {e}",
            }

    def run(self) -> None:
        """Blocking stdio run (legacy). Prefer ``run_gateway_main`` / transport."""
        if _is_stdio_mode and hasattr(sys, "_original_stdout"):
            _saved_stdout = sys.__dict__.get("_original_stdout")
            if _saved_stdout is not None:
                sys.stdout = _saved_stdout
            if os.name == "nt":
                try:
                    import msvcrt

                    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
                except (ImportError, OSError, AttributeError):
                    pass
            sys.stdout.flush()
            os.environ.setdefault("PYTHONUNBUFFERED", "1")
            logging.basicConfig(
                level=logging.CRITICAL,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler(sys.stderr)],
                force=True,
            )
        else:
            logger.info("Starting Beyond Compare MCP Server (FastMCP 3.x)")
            if self.bc_path:
                logger.info("Beyond Compare path: %s", self.bc_path)
            else:
                logger.warning("Beyond Compare executable not found")
        asyncio.run(self.mcp.run_stdio_async())


# --- Fleet unified gateway (FastAPI + FastMCP.from_fastapi) ---

_gateway_start = time.time()
_fleet_initialized = False
_fastapi_app: FastAPI | None = None
_fleet_mcp: FastMCP | None = None
_fleet_core: BeyondCompareMCP | None = None

# Static tool manifest (single source for /api/capabilities + /api/v1/diagnostics).
# FastMCP 3.4.5 exposes no public sync/async get_tools() on the server object
# (only private _list_tools), so the count comes from this list instead of
# a version-fragile private call. Keep in sync with _register_tools().
_ATOMIC_TOOLS = [
    "compare_files",
    "compare_folders",
    "sync_folders",
    "multimedia_drive_scanner",
    "find_multimedia_duplicates",
    "detect_usb_drives",
    "backup_dev_repositories",
    "analyze_dev_workspace",
    "scan_repo_health",
    "cleanup_dev_artifacts",
    "find_duplicate_code",
    "compare_workspace_snapshots",
    "selective_restore",
    "bc_status",
    "bc_help",
    "bc_shutdown",
]
_AGENTIC_TOOLS = ["beyondcompare_agentic_workflow", "beyondcompare_sampling_hint"]


@asynccontextmanager
async def _fleet_lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    from .log_ring import append_log

    append_log({"event": "gateway_startup", "server": "beyondcompare-mcp"})
    yield
    append_log({"event": "gateway_shutdown", "server": "beyondcompare-mcp"})


def _mount_gateway_routes(app: FastAPI, core: BeyondCompareMCP) -> None:
    from ._version import __version__
    from .log_ring import append_log

    @app.middleware("http")
    async def _request_ring(request: Request, call_next: Callable[..., Any]) -> Any:
        t0 = time.time()
        response = await call_next(request)
        append_log(
            {
                "event": "http",
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "ms": int((time.time() - t0) * 1000),
            }
        )
        return response

    @app.get("/api/v1/health")
    async def api_health() -> dict[str, Any]:
        exe = Path(core.bc_path)
        ok_bc = exe.exists()
        return {
            "status": "online",
            "server": {"name": "beyondcompare-mcp", "version": __version__},
            "beyond_compare": {
                "detected": ok_bc,
                "executable": str(core.bc_path),
                "scripts_dir": str(core.scripts_dir),
            },
            "system": {"uptime_s": time.time() - _gateway_start},
            "fleet": {
                "dashboard_frontend": "http://127.0.0.1:10840",
                "gateway_port": int(os.environ.get("MCP_PORT", "10841")),
                "mcp_path": os.environ.get("MCP_PATH", "/mcp"),
            },
        }

    @app.get("/api/v1/diagnostics")
    async def api_diagnostics() -> dict[str, Any]:
        try:
            import psutil  # pyright: ignore[reportMissingModuleSource] - optional dep, ImportError fallback below

            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
        except ImportError:
            cpu = mem = disk = None
        try:
            tool_names = list(_ATOMIC_TOOLS) + list(_AGENTIC_TOOLS)
            tool_total = len(tool_names)
        except Exception:
            tool_total = 0
            tool_names = []
        return {
            "success": True,
            "backend": {
                "port": int(os.environ.get("MCP_PORT", "10841")),
                "status": "running",
                "uptime": int(time.time() - _gateway_start),
            },
            "system": {"cpu_percent": cpu, "memory_percent": mem, "disk_percent": disk},
            "tools": {"total": tool_total, "names": tool_names},
            "cua_status": {"tesseract_available": False, "window_found": False},
        }

    @app.get("/api/capabilities")
    async def api_capabilities() -> dict[str, Any]:
        return {
            "status": "ok",
            "server": {"name": "beyondcompare-mcp", "version": __version__, "fastmcp": "3.x"},
            "tool_surface": {
                "atomic": list(_ATOMIC_TOOLS),
                "agentic": list(_AGENTIC_TOOLS),
            },
            "endpoints": {
                "health": "/api/v1/health",
                "logs": "/api/v1/logs",
                "capabilities": "/api/capabilities",
                "llm_settings": "/api/v1/llm/settings",
                "llm_models": "/api/v1/llm/models",
            },
        }

    def _norm_log(entry: dict[str, Any], idx: int) -> dict[str, Any]:
        import datetime as _dt

        ts = float(entry.get("ts", 0) or 0)
        stamp = _dt.datetime.fromtimestamp(ts).isoformat() if ts else ""
        status = entry.get("status")
        if entry.get("event") == "http":
            detail = f"{entry.get('method', '?')} {entry.get('path', '?')} -> {status} ({entry.get('ms', '?')}ms)"
        else:
            detail = str(entry.get("event", "?"))
            if entry.get("server"):
                detail += f" ({entry.get('server')})"
        level = str(entry.get("level", "")).upper() or (
            "ERROR" if isinstance(status, int) and status >= 500 else "INFO"
        )
        meta = {k: v for k, v in entry.items() if k not in ("ts", "event", "level")}
        return {
            "id": f"{int(ts * 1000) if ts else 0}-{idx}",
            "timestamp": stamp,
            "level": level,
            "kind": str(entry.get("event", "")),
            "detail": detail,
            "meta": meta,
        }

    def _query_logs(
        limit: int = 200,
        offset: int = 0,
        sort: str = "desc",
        level: str = "",
        kind: str = "",
        search: str = "",
        after_id: str = "",
    ) -> dict[str, Any]:
        from .log_ring import get_logs as _get_all

        rows = [_norm_log(e, i) for i, e in enumerate(_get_all(500))]
        if level:
            rows = [r for r in rows if r["level"] == level.upper()]
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        if search:
            q = search.lower()
            rows = [r for r in rows if q in r["detail"].lower() or q in _json_dumps(r["meta"]).lower()]
        rows = sorted(rows, key=lambda r: r["id"], reverse=(sort != "asc"))
        if after_id:
            ids = [r["id"] for r in rows]
            if after_id in ids:
                rows = rows[ids.index(after_id) + 1 :]
        total = len(rows)
        return {"entries": rows[offset : offset + max(limit, 1)], "total": total}

    def _json_dumps(obj: Any) -> str:
        import json as _json

        try:
            return _json.dumps(obj, default=str)
        except Exception:
            return str(obj)

    @app.get("/api/fleet/apps")
    async def api_fleet_apps() -> dict[str, Any]:
        """Fleet app registry for the Apps Hub (mirrors WEBAPP_PORTS.md 10840/10841 entries)."""
        return {
            "apps": [
                {
                    "id": "fleet-dashboard",
                    "label": "Fleet Dashboard",
                    "description": "Central management for all MCP servers",
                    "url": "http://localhost:10794",
                    "port": 10794,
                    "tags": ["infra", "admin"],
                },
                {
                    "id": "advanced-memory",
                    "label": "Advanced Memory",
                    "description": "Semantic knowledge graph and long-term memory",
                    "url": "http://localhost:10704",
                    "port": 10704,
                    "tags": ["ai", "memory"],
                },
                {
                    "id": "robotics",
                    "label": "Robotics Control",
                    "description": "Physical and virtual robot orchestration",
                    "url": "http://localhost:10706",
                    "port": 10706,
                    "tags": ["hardware", "simulation"],
                },
                {
                    "id": "osc-mcp",
                    "label": "OSC Orchestrator",
                    "description": "Real-time media and robotics transport",
                    "url": "http://localhost:10766",
                    "port": 10766,
                    "tags": ["media", "transport"],
                },
                {
                    "id": "obs-mcp",
                    "label": "OBS Dashboard",
                    "description": "Live streaming and recording control",
                    "url": "http://localhost:10818",
                    "port": 10818,
                    "tags": ["media", "streaming"],
                },
                {
                    "id": "ocr-interface",
                    "label": "OCR Interface",
                    "description": "Document scanning and text extraction",
                    "url": "http://localhost:10858",
                    "port": 10858,
                    "tags": ["utilities", "ai"],
                },
                {
                    "id": "winrar",
                    "label": "Archive Manager",
                    "description": "File compression and extraction utilities",
                    "url": "http://localhost:10763",
                    "port": 10763,
                    "tags": ["utility", "files"],
                },
                {
                    "id": "beyondcompare-mcp",
                    "label": "Beyond Compare MCP",
                    "description": "Diff, sync, multimedia scan, and repo health via MCP + REST gateway",
                    "url": "http://localhost:10840",
                    "port": 10840,
                    "tags": ["mcp", "files", "fleet"],
                },
            ],
            "source": "static-registry",
        }

    @app.get("/api/logs")
    @app.get("/api/v1/logs")
    async def api_logs(
        limit: int = 200,
        offset: int = 0,
        sort: str = "desc",
        level: str = "",
        kind: str = "",
        search: str = "",
        after_id: str = "",
    ) -> dict[str, Any]:
        return _query_logs(
            limit=min(limit, 500), offset=offset, sort=sort, level=level, kind=kind, search=search, after_id=after_id
        )

    @app.get("/api/logs/export")
    async def api_logs_export(format: str = "json", level: str = "", kind: str = "", search: str = "") -> Any:
        data = _query_logs(limit=500, level=level, kind=kind, search=search)
        if format == "csv":
            import csv as _csv
            import io as _io

            buf = _io.StringIO()
            w = _csv.writer(buf)
            w.writerow(["id", "timestamp", "level", "kind", "detail"])
            for e in data["entries"]:
                w.writerow([e["id"], e["timestamp"], e["level"], e["kind"], e["detail"]])
            return PlainTextResponse(buf.getvalue(), media_type="text/csv")
        return {"entries": data["entries"], "total": data["total"]}

    @app.delete("/api/logs")
    async def api_logs_clear() -> dict[str, Any]:
        from .log_ring import clear_logs

        return {"ok": True, "dropped": clear_logs()}

    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    llm_store: dict[str, str] = {"provider": "ollama", "model": ""}

    @app.get("/api/v1/llm/settings")
    async def llm_settings_get() -> dict[str, str]:
        return dict(llm_store)

    @app.post("/api/v1/llm/settings")
    async def llm_settings_post(body: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        data = body if isinstance(body, dict) else {}
        model = str(data.get("model") or "").strip()
        provider = str(data.get("provider") or "ollama").strip()
        llm_store["model"] = model
        llm_store["provider"] = provider
        return {"ok": True, "settings": dict(llm_store)}

    @app.get("/api/v1/llm/models")
    async def llm_models() -> dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(f"{ollama_base.rstrip('/')}/api/tags")
                if r.status_code == 200:
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    return {"ok": True, "models": models, "base_url": ollama_base}
        except Exception as e:
            return {"ok": False, "models": [], "error": str(e), "base_url": ollama_base}
        return {"ok": False, "models": [], "base_url": ollama_base}

    @app.get("/api/skills")
    async def api_skills() -> dict[str, Any]:
        """Skill listing for the Chat page (skill-first prompt construction)."""
        from .skills import SKILL_MARKDOWN

        return {
            "skills": [
                {
                    "name": "beyondcompare-mcp",
                    "uri": "skill://beyondcompare-mcp/SKILL.md",
                    "description": "Beyond Compare file/folder comparison, sync, and dev-workspace tools.",
                    "content": SKILL_MARKDOWN,
                }
            ]
        }

    async def _probe_models(base_url: str) -> list[str]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(f"{base_url.rstrip('/')}/api/tags")
                if r.status_code == 200:
                    return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
        except Exception as e:
            logger.debug(f"LLM probe failed for {base_url}: {e}")
        return []

    @app.get("/api/llm/discover")
    async def llm_discover() -> dict[str, Any]:
        """LLM provider auto-discovery (Ollama :11434, LM Studio :1234)."""
        ollama_models = await _probe_models(ollama_base)
        lm_models = await _probe_models("http://127.0.0.1:1234")
        return {
            "ollama": {"detected": bool(ollama_models), "base_url": ollama_base, "models": ollama_models},
            "lm_studio": {"detected": bool(lm_models), "base_url": "http://127.0.0.1:1234", "models": lm_models},
        }

    @app.get("/api/llm/providers")
    async def llm_providers() -> dict[str, Any]:
        """Provider registry shaped for the Settings page (never key bytes — local only)."""
        ollama_models = await _probe_models(ollama_base)
        lm_models = await _probe_models("http://127.0.0.1:1234")
        return {
            "ollama": [{"name": m} for m in ollama_models],
            "lm_studio": [{"name": m} for m in lm_models],
        }

    @app.get("/api/llm/models")
    async def llm_models_standard(provider: str = "ollama") -> dict[str, Any]:
        """Model list per provider (standard path; live when reachable)."""
        base = ollama_base if provider == "ollama" else "http://127.0.0.1:1234"
        models = await _probe_models(base)
        return {"ok": bool(models), "provider": provider, "models": models, "base_url": base}

    async def _resolve_chat_model(data: dict[str, Any]) -> str:
        model = str(data.get("model") or llm_store.get("model") or "").strip()
        if not model:
            models = await _probe_models(ollama_base)
            model = models[0] if models else ""
        return model

    @app.post("/api/llm/chat")
    async def llm_chat(body: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
        """Backend chat proxy (non-streaming) — the only path Chat uses; keys never leave the server."""
        import httpx

        data = body if isinstance(body, dict) else {}
        model = await _resolve_chat_model(data)
        if not model:
            return {"error": "No LLM model available. Start Ollama and pull a model, then retry."}
        messages: list[dict[str, str]] = []
        system = str(data.get("system") or "").strip()
        if system:
            messages.append({"role": "system", "content": system})
        for m in data.get("messages", []) or []:
            if isinstance(m, dict) and m.get("content"):
                messages.append({"role": m.get("role", "user"), "content": str(m["content"])})
        prompt = str(data.get("prompt") or "").strip()
        if prompt:
            messages.append({"role": "user", "content": prompt})
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    f"{ollama_base.rstrip('/')}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                if r.status_code != 200:
                    return {"error": f"Ollama HTTP {r.status_code}: {r.text[:300]}"}
                return {"response": r.json().get("message", {}).get("content", ""), "model": model}
        except Exception as e:
            return _error_response("LLM chat proxy failed", e)

    @app.post("/api/llm/chat/stream")
    async def llm_chat_stream(body: dict[str, Any] | None = Body(default=None)) -> StreamingResponse:
        """Streaming backend chat proxy (SSE `data: {"c": chunk}` + `data: [DONE]`)."""

        async def _gen() -> AsyncIterator[str]:
            import json as _json

            import httpx

            data = body if isinstance(body, dict) else {}
            model = await _resolve_chat_model(data)
            if not model:
                yield 'data: {"error": "No LLM model available. Start Ollama and pull a model."}\n\n'
                yield "data: [DONE]\n\n"
                return
            messages: list[dict[str, str]] = []
            system = str(data.get("system") or "").strip()
            if system:
                messages.append({"role": "system", "content": system})
            for m in data.get("messages", []) or []:
                if isinstance(m, dict) and m.get("content"):
                    messages.append({"role": m.get("role", "user"), "content": str(m["content"])})
            prompt = str(data.get("prompt") or "").strip()
            if prompt:
                messages.append({"role": "user", "content": prompt})
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{ollama_base.rstrip('/')}/api/chat",
                        json={"model": model, "messages": messages, "stream": True},
                    ) as r:
                        if r.status_code != 200:
                            yield f'data: {{"error": "Ollama HTTP {r.status_code}"}}\n\n'
                        else:
                            async for line in r.aiter_lines():
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    payload = _json.loads(line)
                                except Exception:
                                    payload = {}  # non-JSON keepalive line — treated as empty chunk
                                chunk = (
                                    payload.get("message", {}).get("content", "") if isinstance(payload, dict) else ""
                                )
                                if chunk:
                                    yield f"data: {_json.dumps({'c': chunk})}\n\n"
            except Exception as e:
                yield f'data: {{"error": "{str(e)[:200]}"}}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    @app.get("/api/llm/onboarding")
    async def llm_onboarding() -> dict[str, Any]:
        """Fresh-install starter facts + recommended path for the under-hero cue."""
        exe = Path(core.bc_path)
        disc = await llm_discover()
        return {
            "beyond_compare_detected": exe.exists(),
            "ollama_detected": disc["ollama"]["detected"],
            "lm_studio_detected": disc["lm_studio"]["detected"],
            "recommended": (
                "Pick a provider + model on the Settings page, then try the Chat page."
                if (disc["ollama"]["detected"] or disc["lm_studio"]["detected"])
                else "Install Ollama (https://ollama.com) and pull a model, or point BEYOND_COMPARE_PATH at BCompare.exe."
            ),
        }

    @app.post("/api/shutdown")
    async def api_shutdown() -> dict[str, Any]:
        """Orderly exit: respond 200 immediately, exit ~500 ms later (fleet launcher pre-restart hook)."""
        import threading as _threading

        _threading.Timer(0.5, lambda: os._exit(0)).start()
        return {"ok": True, "message": "shutting down"}


def ensure_fleet_stack(
    bc_path: str | None = None,
    scripts_dir: str | None = None,
) -> tuple[FastAPI, FastMCP, BeyondCompareMCP]:
    """Build (once) the FastAPI + FastMCP unified gateway used by stdio, HTTP, and uvicorn."""
    global _fleet_initialized, _fastapi_app, _fleet_mcp, _fleet_core
    if _fleet_initialized and _fastapi_app and _fleet_mcp and _fleet_core:
        return _fastapi_app, _fleet_mcp, _fleet_core

    _backend_port = int(os.environ.get("MCP_PORT", "10841"))
    _cors_origins = [
        # Local dev (registered fleet ports 10840 frontend / 10841 backend)
        "http://localhost:10840",
        "http://127.0.0.1:10840",
        "http://localhost:10841",
        "http://127.0.0.1:10841",
        # Tauri WebView (always include, harmless when not in Tauri)
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ]
    _cors_regex = (
        r"https?://(?:[a-zA-Z0-9-]+\.ts\.net|.*?\.tail-[a-f0-9]+\.ts\.net"
        r"|tauri\.localhost|localhost|127\.0\.0\.1"
        r"|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|100\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?$|^tauri://localhost$"
    )
    fastapi_app = FastAPI(title="Beyond Compare MCP", lifespan=_fleet_lifespan)
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_origin_regex=_cors_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    mcp = FastMCP.from_fastapi(fastapi_app, name="Beyond Compare MCP")
    core = BeyondCompareMCP(bc_path=bc_path, scripts_dir=scripts_dir, mcp=mcp)
    _mount_gateway_routes(fastapi_app, core)

    from .agentic import register_agentic_tools, set_core_getter
    from .prompts import register_prompts
    from .skills import register_skill_resources

    register_prompts(mcp)
    register_skill_resources(mcp)
    set_core_getter(lambda: core)
    register_agentic_tools(mcp)

    # Mount MCP streamable HTTP on the gateway. from_fastapi() only converts
    # routes into tools — without this mount POST /mcp 404s while stdio works,
    # and HTTP peers (e.g. disk-usage-mcp's BC crossconnect) fail at init.
    # Mirrors disk-usage-mcp's build_app: path="/" avoids the double prefix,
    # sub-app lifespan entered inside the parent lifespan.
    from contextlib import asynccontextmanager

    mcp_path = os.environ.get("MCP_PATH", "/mcp")
    if not any(getattr(r, "path", "") == mcp_path for r in fastapi_app.routes):
        mcp_http = mcp.http_app(path="/")

        @asynccontextmanager
        async def _combined_lifespan(parent: FastAPI) -> AsyncIterator[None]:
            async with _fleet_lifespan(parent):
                async with mcp_http.lifespan(parent):
                    yield

        fastapi_app.router.lifespan_context = _combined_lifespan
        fastapi_app.mount(mcp_path, app=mcp_http)

    _fastapi_app = fastapi_app
    _fleet_mcp = mcp
    _fleet_core = core
    _fleet_initialized = True
    return fastapi_app, mcp, core


def get_fleet_mcp() -> FastMCP:
    return ensure_fleet_stack()[1]


def reset_fleet_stack_for_tests() -> None:
    """Clear gateway singletons (pytest only)."""
    global _fleet_initialized, _fastapi_app, _fleet_mcp, _fleet_core
    _fleet_initialized = False
    _fastapi_app = None
    _fleet_mcp = None
    _fleet_core = None


class _LazyFleetASGI:
    """Defer Beyond Compare discovery until first HTTP/MCP request or explicit init."""

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        real_app, _, _ = ensure_fleet_stack()
        await real_app(scope, receive, send)


app = _LazyFleetASGI()


def run_gateway_main(argv: list[str] | None = None) -> None:
    """CLI / ``python -m beyondcompare_mcp.server`` entry with fleet transport flags."""
    from .transport import create_argument_parser, run_server

    if not _is_stdio_mode:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )

    parser = create_argument_parser("beyondcompare-mcp")
    parser.add_argument(
        "--bc-path",
        type=str,
        default=settings.BEYOND_COMPARE_PATH,
        help="Path to Beyond Compare executable (default: settings / env / auto-detect)",
    )
    parser.add_argument(
        "--scripts-dir",
        type=str,
        default=settings.BC_SCRIPTS_DIR,
        help="Directory for temporary BC scripts (default: settings / env)",
    )
    args = parser.parse_args(argv)
    ensure_fleet_stack(
        bc_path=args.bc_path,
        scripts_dir=args.scripts_dir,
    )
    # Import-time stdio mode swaps sys.stdout for DevNullStdout; only the legacy
    # BeyondCompareMCP.run() restored it, so on this path every JSON-RPC reply
    # went into the sink and clients never got an initialize response.
    if hasattr(sys, "_original_stdout"):
        _saved_stdout = sys.__dict__.get("_original_stdout")
        if _saved_stdout is not None:
            sys.stdout = _saved_stdout
    run_server(get_fleet_mcp(), args=args, server_name="beyondcompare-mcp")


def main() -> None:
    run_gateway_main()


if __name__ == "__main__":
    main()
