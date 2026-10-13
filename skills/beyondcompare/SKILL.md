# Beyond Compare MCP — operator skill

## Who this is for

- **Agents**: call the atomic tools directly with absolute Windows paths.
  Use `beyondcompare_agentic_workflow(goal="...")` only when the host
  supports `ctx.sample()`; otherwise sequence atomic tools yourself.
- **Humans**: the web dashboard (:10840) covers compare, sync, chat, logs,
  and settings. Anything destructive runs preview-first.

## Tool catalog (real operation names)

Read-only: `compare_files`, `compare_folders`, `multimedia_drive_scanner`,
`find_multimedia_duplicates`, `detect_usb_drives`, `find_duplicate_code`,
`compare_workspace_snapshots`, `bc_status`, `bc_help`.
Mutating: `backup_dev_repositories`, `analyze_dev_workspace`,
`scan_repo_health` (mutating only with `fix_issues=True`).
Destructive: `sync_folders` (mirror deletes target-only files),
`cleanup_dev_artifacts`, `selective_restore`, `bc_shutdown`.
Agentic: `beyondcompare_agentic_workflow`, `beyondcompare_sampling_hint`.

Gateway REST (backend :10841): `GET /api/v1/health`,
`GET /api/v1/diagnostics`, `GET /api/capabilities`, `GET /api/skills`,
`GET /api/logs` (+ `/export`, `DELETE`), `GET /api/fleet/apps`,
`GET /api/llm/discover|providers|models|onboarding`,
`POST /api/llm/chat|chat/stream`, `POST /api/shutdown`.

## Workflow 1 — verify a backup

1. `compare_folders(left_path='D:/ live', right_path='E:/backup')`
   with `include_subfolders=True`.
2. If `differences_found` is false, stop — backup is current.
3. Otherwise write `output_report` to a dated file and review before syncing.

## Workflow 2 — safe folder sync

1. `sync_folders(source_path, target_path, sync_mode='mirror', dry_run=True)`.
2. Read `changes_detected` + message. Never skip the preview.
3. Re-run with `dry_run=False` only after the user confirms.
4. Prefer `update` over `mirror` when the target holds files the source lacks.

## Workflow 3 — reclaim media space

1. `multimedia_drive_scanner(file_types=['video'])` to inventory.
2. `find_multimedia_duplicates(min_size_mb=100, use_content_hash=True)`.
3. Work the largest `duplicate_groups` first; keep the lowest drive letter.

## Workflow 4 — workspace hygiene pass

1. `scan_repo_health(repos_path='D:/Dev/repos')` report-only.
2. `cleanup_dev_artifacts(repos_path='D:/Dev/repos', dry_run=True)`.
3. Execute cleanup only on confirmation; then `backup_dev_repositories`
   with `compress=True, incremental=True`.

## Troubleshooting

- `BeyondCompareNotInstalledError`: set `BEYOND_COMPARE_PATH` to
  `BCompare.exe` (BC5 path works) and restart the gateway.
- Chat errors with "No LLM model available": start Ollama, `ollama pull`
  a model, reselect it on the Settings page. Chat proxies through
  `POST /api/llm/chat/stream` — it never calls Ollama directly.
- Dashboard offline: `.\start.ps1 -BackendOnly`, then
  `GET http://127.0.0.1:10841/api/v1/health`.

## Configuration

Env: `BEYOND_COMPARE_PATH`, `LOG_LEVEL`, `BC_SCRIPTS_DIR`,
`COMMAND_TIMEOUT`, `MCP_PORT` (10841), `MCP_PATH` (/mcp),
`OLLAMA_BASE_URL`, `MCP_BRIDGE_URLS` (optional proxy list).
See `docs/CONFIGURATION.md`. Ports: frontend 10840, backend 10841.
