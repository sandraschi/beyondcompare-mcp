# Troubleshooting — beyondcompare-mcp

## Dashboard shows offline

1. Start the backend: `.\start.ps1 -BackendOnly`
2. Probe: `GET http://127.0.0.1:10841/api/v1/health` must return 200.
3. The frontend uses same-origin `/api/...` (vite proxy). If you opened
   the UI via a LAN/Tailscale hostname and calls fail, that is CORS
   working as designed for absolute URLs — use the local URL or Tauri app.

## Beyond Compare not detected

`GET /api/v1/health` → `beyond_compare.detected: false`.
Set `BEYOND_COMPARE_PATH` to the full `BCompare.exe` path (BC5 default:
`C:\Program Files\Beyond Compare 5\BCompare.exe`) and restart the gateway.

## Chat errors

- "No LLM model available": start Ollama (`ollama serve`), pull a model
  (`ollama pull llama3.2:3b`), reselect provider + model on Settings.
- Chat proxies through `POST /api/llm/chat/stream` — the browser never
  calls Ollama directly. A 500 there means the backend cannot reach
  `OLLAMA_BASE_URL`.

## MCP client cannot reach /mcp (404)

The gateway mounts `mcp.http_app(path="/")` at `MCP_PATH` (`/mcp`).
Verify with a real client (`fastmcp.Client("http://127.0.0.1:10841/mcp")`
→ `list_tools()`), not just `/health` — path and lifespan bugs only
show under a real MCP session.

## Port already in use

`.\start.ps1` clears :10840/:10841 zombie listeners before binding
(fleet engine). If a foreign process holds the port, the engine reports
the PID — stop it, then relaunch.

## Tests

`uv run pytest tests/ -q --ignore=tests/test_integration.py`
(23 passed, 26 skipped is the healthy baseline — skips are
Beyond-Compare-absent / platform-gated cases).
