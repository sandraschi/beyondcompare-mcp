"""SEP-1577 agentic workflow (sampling) for Beyond Compare MCP."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

logger = logging.getLogger("beyondcompare_mcp.agentic")

_get_core: Callable[[], Any] | None = None


def set_core_getter(fn: Callable[[], Any]) -> None:
    global _get_core
    _get_core = fn


def register_agentic_tools(mcp: FastMCP) -> None:
    """Register sampling workflow + static sampling hint."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def beyondcompare_sampling_hint() -> str:
        """Explain how to use client-side sampling with this server (SEP-1577).

        ## Return Format
        Plain-text hint string describing the sampling workflow and fallback.

        ## Examples
        beyondcompare_sampling_hint()
        """
        return (
            "beyondcompare_agentic_workflow uses FastMCP Context.sample() so the host model can "
            "plan and call sub-tools (bc_status, compare_two_files, compare_two_folders, scan_repos). "
            "Requires an MCP client that implements tool sampling (e.g. Cursor with sampling enabled). "
            "If sampling is not available, invoke compare_files, compare_folders, and scan_repo_health directly."
        )

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})
    async def beyondcompare_agentic_workflow(
        goal: Annotated[
            str,
            Field(
                description=(
                    "Natural-language goal, e.g. 'Compare D:/a/file.txt vs D:/b/file.txt and say if identical' "
                    "or 'Scan D:/Dev/repos for git health issues'."
                ),
            ),
        ],
        ctx: Context,
    ) -> str:
        """Plan and execute BC-focused steps via sampling (SEP-1577).

        ## Return Format
        Plain-text summary of the executed plan and results.

        ## Examples
        beyondcompare_agentic_workflow(
            goal='Compare D:/a/file.txt vs D:/b/file.txt and say if identical')
        """

        def core() -> Any:
            if _get_core is None:
                raise RuntimeError("Beyond Compare MCP core getter not configured")
            return _get_core()

        async def bc_status() -> str:
            c = core()
            return json.dumps(
                {
                    "bc_path": str(c.bc_path),
                    "scripts_dir": str(c.scripts_dir),
                }
            )

        async def compare_two_files(
            left_path: str,
            right_path: str,
            output_report: str | None = None,
        ) -> str:
            out = core()._compare_files(left_path, right_path, output_report)
            return json.dumps(out)

        async def compare_two_folders(
            left_path: str,
            right_path: str,
            include_subfolders: bool = True,
            output_report: str | None = None,
        ) -> str:
            out = core()._compare_folders(
                left_path,
                right_path,
                output_report,
                include_subfolders,
            )
            return json.dumps(out)

        async def scan_repos(repos_path: str) -> str:
            out = core().health_checker.scan_repository_health(
                repos_path,
                checks=None,
                report_path=None,
                fix_issues=False,
            )
            return json.dumps(out)

        system_prompt = (
            "You operate Beyond Compare MCP tools through these functions: "
            "bc_status(), compare_two_files(left_path, right_path, output_report optional), "
            "compare_two_folders(left_path, right_path, include_subfolders, output_report optional), "
            "scan_repos(repos_path). "
            "Use bc_status first. Prefer dry, read-only steps unless the user explicitly asked to sync or delete. "
            "Summarize JSON results in plain language."
        )
        try:
            result = await ctx.sample(
                messages=goal,
                system_prompt=system_prompt,
                tools=[bc_status, compare_two_files, compare_two_folders, scan_repos],
                temperature=0.2,
                max_tokens=2048,
            )
            return result.text or "No response from planner."
        except Exception as e:
            logger.exception("beyondcompare_agentic_workflow failed")
            return f"Workflow failed: {e}"
