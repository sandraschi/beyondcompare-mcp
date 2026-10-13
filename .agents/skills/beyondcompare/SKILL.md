---
name: beyondcompare
description: Beyond Compare session start prompt — diff, sync, and workspace tools
---

## Session Context (Beyond Compare MCP)

File/folder diff, sync, and dev-workspace tools via Beyond Compare 5.

**Before starting work:**
1. Check engine status: bc_status()
2. For diffs: compare_files(left_path="...", right_path="...") or compare_folders(left_path="...", right_path="...")
3. Preview syncs first: sync_folders(source_path="...", target_path="...", dry_run=True)

**At end of work:**
- Multi-step goals: beyondcompare_agentic_workflow(goal="...")
- Gateway health: GET http://127.0.0.1:10841/api/v1/health

## Tool catalog

Atomic (read-only unless noted): compare_files, compare_folders,
multimedia_drive_scanner, find_multimedia_duplicates, detect_usb_drives,
find_duplicate_code, compare_workspace_snapshots.
Mutating: backup_dev_repositories, analyze_dev_workspace, scan_repo_health.
Destructive: sync_folders (mirror deletes), cleanup_dev_artifacts,
selective_restore, bc_shutdown.
Local: bc_status, bc_help. Agentic: beyondcompare_agentic_workflow,
beyondcompare_sampling_hint (needs sampling-capable client).
