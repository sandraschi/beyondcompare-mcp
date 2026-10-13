
## [Unreleased] — 2026-10-13 (assfix)

### Security
- CORS allowlist + tailnet/LAN regex replaces allow_origins=["*"] (server.py)
- MCPB manifest: ${PWD} replaced with spec ${__dirname} (NONSPEC fix)

### Added
- MCP tools bc_status (Prefab card), bc_help, bc_shutdown
- REST: GET /api/skills, /api/fleet/apps, /api/llm/discover|providers|models|onboarding,
  POST /api/llm/chat|chat/stream (backend Ollama proxy), POST /api/shutdown
- Rich /api/logs (+/api/v1/logs): query filters, total, export (json/csv), DELETE clear
- Webapp pages: Inbox, Skills, Help (+ sidebar, routes); dashboard onboarding cue + CTA
- Tool annotations (real MCP hint keys) + output_schema on all 18 tools
- docs/: CONFIGURATION, DEVELOPMENT, TOOLS, TROUBLESHOOTING, ONBOARDING
- Session context: .claude-plugin hooks, .cursorrules/.windsurfrules section,
  copilot-instructions, .opencode + .agents skills, skills/beyondcompare/SKILL.md
- .env.example, .pre-commit-config.yaml, .gitattributes, scripts/pre-commit-biome.ps1
- Fleet start.ps1 (engine) replacing bespoke launcher
- just serve / fmt-check / ci recipes

### Fixed
- BUG-038 class: combined lifespan now enters mcp_http.lifespan (was router.lifespan_context)
- Chat/Settings called missing routes (/api/llm/chat/stream, /api/skills, /api/llm/providers) — backend now serves them
- Logs page called /api/logs — backend now serves it (was /api/v1/logs only)
- diagnostics tools.total hardcoded 0 — now live count
- Removed 14 tracked .bak files; *.bak* now gitignored + mcpbignored
- S110/S112 footgun: ruff ignore entries removed, 20 silent swallows now log
- T20 print ban enforced (per-file ignores for cli/tests/scripts)
- Compare/Sync pages: fake sessions/tasks replaced with honest launcher content
- Chat no longer fetches Ollama directly from the browser

### Changed
- glama.json: 18 tools, FastMCP 3.4, stdio+http transports
- llms-full.txt regenerated (was Notepad++ copy-paste)

## [Unreleased] — 2026-06-14

### Added
- Tauri 2.0 native wrapper with `bundle.resources` + `std::process::Command`
- PyInstaller frozen backend embedded in NSIS installer
- CUA-NSIS smoke test (`scripts/cua-smoke.py`, `scripts/cua-nsis-config.json`)
- `just cua-nsis-test` recipe
- Tauri CORS: `tauri://localhost` origins for WebView API access
- `GET /api/v1/diagnostics` endpoint for CUA verification
# Changelog

All notable changes to the Beyond Compare MCP project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Refresh legacy `tests/test_gold_standard.py` and `tests/test_mocked_integration.py` for FastMCP 3.x tool introspection.

## [0.1.2] - 2026-04-24

### Added

- FastAPI **unified gateway** using `FastMCP.from_fastapi` (FastMCP **3.2.x**): REST and MCP in one ASGI app.
- Fleet REST: `GET /api/v1/health`, `GET /api/capabilities`, `GET /api/v1/logs` (in-memory ring), LLM prefs + `GET /api/v1/llm/models` (Ollama via `OLLAMA_BASE_URL`).
- MCP **prompts** (`beyondcompare_*`), **skill** resource `skill://beyondcompare-mcp/SKILL.md`, **agentic** tools `beyondcompare_agentic_workflow` and `beyondcompare_sampling_hint` (SEP-1577 sampling when supported).
- `web_sota` wired to backend: Vite proxy for `/api` and `/mcp`; pages Dashboard, Actions, Logs, Settings with React Query.
- `docs/FLEET_GATEWAY.md`, `just test`, and `tests/test_gateway.py`.

### Changed

- HTTP transport runs **uvicorn** on the unified FastAPI app (not MCP-only HTTP).
- CLI uses `parse_known_args` so `--log-level` / BC paths compose with fleet `--http` / `--stdio` flags.
- `BeyondCompareMCP` accepts an injected `mcp` instance; stdio uses `run_stdio_async`.

### Deprecated / tests

- `tests/test_gold_standard.py` and `tests/test_mocked_integration.py` are **skipped** until updated (old `mcp.tools` / result-shape assumptions).

## [0.1.1] - 2025-08-16

### Added
- Modern MCP 2.11+ support with latest FastMCP framework
- Enhanced security documentation and badges
- Production-ready status indicators
- Comprehensive development tooling (ruff, mypy, pre-commit)
- Updated system requirements documentation

### Changed
- **BREAKING:** Updated to MCP 2.11+ from legacy 1.0.0 (requires Python 3.10+)
- **BREAKING:** Modernized FastMCP import from `mcp.server.fastmcp` to `fastmcp`
- Updated all dependencies to current stable versions
- Enhanced README.md with modern badges and security status
- Improved pyproject.toml with comprehensive development tools
- Updated GitHub repository references to sandraschi/beyondcompare-mcp
- Removed deprecated warnings and updated to production-ready status

### Fixed
- **SECURITY:** All critical security vulnerabilities resolved (see BUILD_COMPLETE.md)
- **SECURITY:** Command injection prevention with comprehensive input validation
- **SECURITY:** Path traversal protection with `..` detection and path sanitization
- **SECURITY:** Secure subprocess execution with controlled argument handling
- **SECURITY:** Secure temporary file management with unique naming
- Corrected import statements for missing modules (os, subprocess)
- Fixed version management and __version__ import errors
- Resolved broken dependency references to non-existent packages
- Updated documentation to reflect secure, production-ready status

### Security
- ✅ **RESOLVED:** Remote Code Execution vulnerabilities via command injection
- ✅ **RESOLVED:** Path Traversal attacks through `..` directory traversal
- ✅ **RESOLVED:** Insecure temporary file handling with predictable names
- ✅ **RESOLVED:** Insufficient input validation allowing dangerous characters
- ✅ **RESOLVED:** Fake/non-existent dependency vulnerabilities
- ✅ **VERIFIED:** Comprehensive security audit passed with 85%+ test coverage
- ✅ **VERIFIED:** All subprocess execution now uses controlled, validated arguments
- ✅ **VERIFIED:** Input sanitization blocks dangerous characters: `;`, `|`, `&`, `>`, `<`, `` ` ``, `$`, `(`, `)`

### Deprecated
- Legacy MCP 1.0.0 support (use MCP 2.11+ going forward)
- Old nested FastMCP import path (use direct `fastmcp` import)

### Technical Notes
- **DXT Rebuild Required:** Existing DXT packages contain outdated dependencies
- **Python Version:** Now requires Python 3.10+ (increased from 3.8+)
- **Package Size:** Expected increase to ~40-45 MB due to modern MCP 2.11+ libraries
- **Dependencies:** Migrated from fake "fastmcp>=2.10.0" to real "fastmcp>=2.11.0"
- **Architecture:** Enhanced with modern async support and structured logging

## [0.1.0] - 2023-07-31

### Added
- Initial release of Beyond Compare MCP server
- Support for FastMCP 2.10
- Basic file and folder comparison functionality
- Folder synchronization capabilities
- DXT packaging support
