"""MCP resources exposing bundled skill text (skill:// URI)."""

from __future__ import annotations

from fastmcp import FastMCP

SKILL_MARKDOWN = """# Beyond Compare MCP - operator skill

## When to use which tool
- **compare_files** - two files, optional text report path.
- **compare_folders** - trees; set `include_subfolders` false for shallow passes.
- **sync_folders** - always **dry_run** first; modes: mirror | update | backup.
- **scan_repo_health** - many git checkouts under one parent path.
- **cleanup_dev_artifacts** - keep `dry_run=true` until the user confirms deletes.
- **multimedia_drive_scanner / find_multimedia_duplicates** - large media libraries.

## Fleet integration
- HTTP gateway (optional): MCP streamable and REST share one process.
- **GET /api/v1/health** - process + Beyond Compare detection.
- **GET /api/v1/logs** - recent HTTP/API activity ring buffer.
- **GET /api/capabilities** - static capability manifest for dashboards.

## Agentic + sampling
- Use **beyondcompare_agentic_workflow** for natural-language goals when the client supports `ctx.sample`.
- If sampling is unavailable, call atomic tools in sequence and narrate results.

## Safety
- Reject path traversal and command injection; prefer absolute paths on Windows.
"""


def register_skill_resources(mcp: FastMCP) -> None:
    @mcp.resource("skill://beyondcompare-mcp/SKILL.md", mime_type="text/markdown")
    def beyondcompare_skill() -> str:
        """Bundled operator guidance for agents."""
        return SKILL_MARKDOWN
