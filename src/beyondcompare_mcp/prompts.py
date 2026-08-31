"""Native FastMCP prompts for Beyond Compare MCP (fleet parity)."""

from __future__ import annotations

from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register prompts exposed over MCP."""

    @mcp.prompt()
    def beyondcompare_quick_start(workspace_root: str = "D:/Dev/repos") -> str:
        """How to compare folders and run repo health with this MCP server."""
        return f"""You are helping a developer use Beyond Compare MCP.

1. Ensure Beyond Compare 4+ is installed. Optional: set BEYOND_COMPARE_PATH to BCompare.exe.
2. Fleet dashboard (if running HTTP): frontend http://127.0.0.1:10840 - API http://127.0.0.1:10841/api/v1/health
3. For a quick folder diff: call compare_folders(left_path, right_path, include_subfolders=true).
4. For repo hygiene across clones: call scan_repo_health(repos_path='{workspace_root}').
5. For multi-step goals use beyondcompare_agentic_workflow(goal=...) when sampling is available (SEP-1577)."""

    @mcp.prompt()
    def beyondcompare_backup_sync() -> str:
        """Plan backup and sync using BC-backed tools."""
        return """Plan a safe backup or sync:

1. Optionally analyze_dev_workspace(workspace_path) for size and languages.
2. For directory sync, use sync_folders with dry_run=true first, then dry_run=false after review.
3. For full-tree backups, backup_dev_repositories with dry_run=true, then run for real.
4. Never delete data without explicit user confirmation; prefer dry_run and reports."""

    @mcp.prompt()
    def beyondcompare_multimedia_inventory() -> str:
        """Drive scan and duplicate workflow for multimedia tools."""
        return """Multimedia workflow:

1. Run multimedia_drive_scanner() to refresh inventory (optionally pass drives=['E:','F:']).
2. Run find_multimedia_duplicates(use_content_hash=false) for a fast pass, then true for accuracy.
3. Use detect_usb_drives before copying large sets to removable media."""
