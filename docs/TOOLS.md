# Tools — beyondcompare-mcp

16 atomic + local + 2 agentic = 18 MCP tools. Full signatures live in
`src/beyondcompare_mcp/server.py` (`## Return Format` + `## Examples`
per tool); this page is the index.

## Comparison (read-only)

- `compare_files(left_path, right_path, output_report?)` — quick-compare
  two files (size + timestamp), optional text report.
- `compare_folders(left_path, right_path, output_report?, include_subfolders=True)`
  — tree diff with orphan/different counts.

## Sync (destructive)

- `sync_folders(source_path, target_path, sync_mode='mirror', dry_run=True)` —
  modes `mirror` (exact, deletes extras), `update` (incremental),
  `backup` (fill missing only). Always preview first.

## Multimedia (read-only)

- `multimedia_drive_scanner(drives?, recent_days?, file_types?)` —
  inventory of E:/F:/K:/L: media libraries (cached for dedup).
- `find_multimedia_duplicates(drives?, min_size_mb=0.1, file_types?, use_content_hash=True)`
- `detect_usb_drives()` — removable drives + free space.

## Dev workspace

- `backup_dev_repositories(source_path, backup_path, exclude_patterns?, include_git_essentials=True, compress=True, incremental=True, dry_run=False)` (mutating)
- `analyze_dev_workspace(workspace_path, report_path?, include_git_stats?, include_dependencies?, include_size_analysis?)` (mutating — writes HTML report)
- `scan_repo_health(repos_path, checks?, report_path?, fix_issues=False)` (mutating when fixing)
- `cleanup_dev_artifacts(repos_path, targets?, size_threshold_mb=100, dry_run=True)` (destructive)
- `find_duplicate_code(repos_path, file_types?, min_lines=10, similarity_threshold=0.8, report_path?)` (read-only)
- `compare_workspace_snapshots(snapshot1_path, snapshot2_path, report_path?, show_changes?)` (read-only)
- `selective_restore(backup_path, restore_items, target_path, preserve_structure=True, overwrite_existing=False)` (destructive)

## Local

- `bc_status()` — detection + tool count + uptime (Prefab card).
- `bc_help(topic?)` — this catalog, or one tool's guidance.
- `bc_shutdown()` — orderly exit (~500 ms).

## Agentic (needs sampling-capable client)

- `beyondcompare_agentic_workflow(goal, ctx)` — plans via `ctx.sample()`.
- `beyondcompare_sampling_hint()` — usage hint string.

## REST (backend :10841)

Health/diagnostics/capabilities/skills/logs/fleet-apps/llm/* under
`/api/...` — see Help page → Tool surface, or `GET /api/capabilities`.
