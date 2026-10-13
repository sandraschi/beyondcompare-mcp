# Configuration — beyondcompare-mcp

All settings are environment variables (see `.env.example`). Copy it to
`.env` for local overrides; never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `BEYOND_COMPARE_PATH` | auto-detect (BC5 → BC4 → BC3 → PATH) | Full path to `BCompare.exe` / `bcompare` |
| `LOG_LEVEL` | `INFO` | Python log level |
| `BC_SCRIPTS_DIR` | `./bc_scripts` | Temp Beyond Compare script files |
| `COMMAND_TIMEOUT` | `30` | Subprocess timeout (seconds) |
| `MCP_PORT` | `10841` | Gateway backend port (must match `fleet-start.config.ps1`) |
| `MCP_PATH` | `/mcp` | MCP streamable-HTTP mount path |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local LLM for the Chat proxy |
| `MCP_BRIDGE_URLS` | empty | Comma-separated MCP servers to proxy (optional) |
| `WEB_PORT` | `10841` | Set by the launcher; informational |

Ports (fleet registry `WEBAPP_PORTS.md`): frontend **10840** (Vite),
backend **10841** (FastAPI + FastMCP gateway).

Claude Desktop (stdio) — `claude_desktop_config.json`:

```json
"beyondcompare-mcp": {
  "command": "uv",
  "args": ["--directory", "D:/Dev/repos/beyondcompare-mcp", "run", "beyondcompare-mcp"]
}
```
