# Development — beyondcompare-mcp

## Setup

```powershell
just bootstrap        # uv sync + pre-commit install
just serve            # backend gateway only (:10841)
# frontend in another shell:
cd web_sota; npm run dev   # :10840, proxies /api + /mcp
```

Full stack: `.\start.ps1` (fleet engine). Backend only:
`.\start.ps1 -BackendOnly`.

## Gates

```powershell
just ci               # ruff check + format check + pytest
uv run pytest tests/ -q --ignore=tests/test_integration.py
npx tsc --noEmit      # from web_sota/
npx biome check web_sota/src/
```

Python: `uv run ruff check src/`, `uv run ruff format src/`.
Type checking is mypy-flavored config in `pyproject.toml`
(`[tool.mypy]`); pyright is intentionally not wired (stdlib-only
surface, FastMCP dynamic tools).

## Layout

- `src/beyondcompare_mcp/server.py` — FastAPI + FastMCP unified gateway
  (`ensure_fleet_stack`), all MCP tools, all REST routes.
- `src/beyondcompare_mcp/tools/developer/` — backup/analyzer/health/duplicates.
- `src/beyondcompare_mcp/multimedia_scanner.py` — drive inventory + hashing.
- `src/beyondcompare_mcp/agentic.py` — SEP-1577 sampling workflow.
- `src/beyondcompare_mcp/skills.py`, `prompts.py` — skill:// resource + prompts.
- `web_sota/` — React + Vite + Tailwind + Zustand dashboard.
- `native/` — Tauri 2 wrapper (targets: nsis).

## Conventions

- Tool returns are dialogic: always `success` + `message`.
- Docstrings carry `## Return Format` + `## Examples`.
- Annotations use real MCP hint keys (`readOnlyHint`, `destructiveHint`,
  `openWorldHint`); `output_schema={"type": "object"}` on dict tools.
- Never `except: pass` — log (`logger.debug` for probes,
  `logger.exception` in error paths). T20: no `print()` in `src/`
  (CLI `cli.py` has a per-file ignore).
- Frontend calls the backend same-origin (`API_BASE = ""`), absolute
  only inside Tauri. Never fetch Ollama from the browser — use
  `POST /api/llm/chat/stream`.
