# Onboarding — beyondcompare-mcp

Get from zero to first diff in ~10 minutes.

## 1. What this is for

Compare files/folders, sync directories, scan media libraries, and keep
dev checkouts healthy — through MCP tools (Claude/Cursor), a Python API,
or the web dashboard (:10840).

## 2. Prerequisites

- Python 3.12+ via `uv` (see AGENT_INSTALL_REFERENCE).
- Node 22+ for the dashboard (`cd web_sota; npm install`).
- **Beyond Compare 4+** (BC5 verified). Install from
  https://www.scootersoftware.com/ — the gateway auto-detects it.
  No account, no license key for the MCP server itself (BC needs its own
  license for full features; the free trial works for evaluation).

## 3. Sanity check

```powershell
just bootstrap
just serve   # backend :10841
```

Open http://127.0.0.1:10840 — the red **Finish setup** cue under the
hero disappears once Beyond Compare is detected AND a local LLM answers.

## 4. Pitfalls

- Dashboard offline but backend runs: you opened the UI via a hostname
  the vite proxy does not cover — use `http://127.0.0.1:10840`.
- `BCompare.exe` not found: set `BEYOND_COMPARE_PATH` in `.env`.
- Chat needs Ollama (`ollama serve` + `ollama pull <model>`); the
  dashboard never talks to Ollama directly.

## 5. First tasks

1. Compare two folders (AI Command page): "Compare D:/a vs D:/b".
2. Preview a sync: `sync_folders(..., dry_run=True)` — always preview.
3. Scan repo health: `scan_repo_health(repos_path='D:/Dev/repos')`.
