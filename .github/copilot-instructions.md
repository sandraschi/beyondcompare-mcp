## Session Context (Beyond Compare MCP)

File/folder diff, sync, and dev-workspace tools via Beyond Compare 5.

**Before starting work:**
1. Check engine status: bc_status()
2. For diffs: compare_files(left_path="...", right_path="...") or compare_folders(left_path="...", right_path="...")
3. Preview syncs first: sync_folders(source_path="...", target_path="...", dry_run=True)

**At end of work:**
- Multi-step goals: beyondcompare_agentic_workflow(goal="...")
- Gateway health: GET http://127.0.0.1:10841/api/v1/health
