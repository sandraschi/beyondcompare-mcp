"""Route contract: every /api/* path the webapp references must exist on the backend.

Pain point since 2025: the frontend called /api/v1/capabilities while the
backend served /api/capabilities — every Actions visit 404'd and unmounted
the whole React tree (black window). Neither assfix 1E (backend-side list)
nor eyeballing catches this; this test does, mechanically, on every run.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB_SOTA_SRC = Path(__file__).parent.parent / "web_sota" / "src"

# A quoted string literal whose content starts with /api/, e.g.
# "/api/skills", `${API_BASE}/api/logs?...`, '/api/llm/chat'.
_LITERAL_RE = re.compile(r"""["'`](\/api\/[^"'`\s]*)""")

# Entries of the ENDPOINTS map in web_sota/src/lib/api.ts.
_ENDPOINT_RE = re.compile(r"""^\s*(\w+):\s*"(\/api\/[^"]*)",?\s*$""", re.MULTILINE)


def _strip(path: str) -> str | None:
    """Normalize a raw literal to a route path, or None when not a route."""
    path = path.split("?")[0].split("${")[0].rstrip("/")
    if not path.startswith("/api/"):
        return None
    if "..." in path:
        return None  # ellipsis placeholder inside comments/docs
    return path or None


def frontend_references() -> dict[str, set[str]]:
    """Map route path -> set of source files referencing it."""
    found: dict[str, set[str]] = {}
    for f in sorted(WEB_SOTA_SRC.rglob("*")):
        if f.suffix not in (".ts", ".tsx"):
            continue
        if "node_modules" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _LITERAL_RE.finditer(text):
            route = _strip(m.group(1))
            if route:
                found.setdefault(route, set()).add(f.name)
    # Every ENDPOINTS value must also resolve (pages reference them by name).
    api_ts = WEB_SOTA_SRC / "lib" / "api.ts"
    for m in _ENDPOINT_RE.finditer(api_ts.read_text(encoding="utf-8")):
        route = _strip(m.group(2))
        if route:
            found.setdefault(route, set()).add("lib/api.ts(ENDPOINTS)")
    return found


def backend_routes() -> set[str]:
    """Route paths registered on the real FastAPI gateway."""
    from beyondcompare_mcp.server import ensure_fleet_stack

    app, _, _ = ensure_fleet_stack()
    return {getattr(r, "path", "") for r in app.routes if getattr(r, "path", "").startswith("/api")}


def test_frontend_routes_exist_on_backend(tmp_path: Path) -> None:
    import beyondcompare_mcp.server as srv

    # Backend construction requires a Beyond Compare executable; use a fake
    # so the contract holds on machines without BC installed.
    fake = tmp_path / "BCompare.exe"
    fake.write_bytes(b"\x00\x00")
    scripts = tmp_path / "bcscripts"
    scripts.mkdir(exist_ok=True)
    srv.reset_fleet_stack_for_tests()
    srv.ensure_fleet_stack(bc_path=str(fake), scripts_dir=str(scripts))

    routes = backend_routes()
    refs = frontend_references()
    assert refs, "no frontend route references found - scanner broken?"
    missing = {p: sorted(fs) for p, fs in sorted(refs.items()) if p not in routes}
    assert not missing, "frontend calls routes the backend does not serve: " + "; ".join(
        f"{p} (from {', '.join(fs)})" for p, fs in missing.items()
    )


def test_endpoints_map_covers_fetch_helpers() -> None:
    """Every fetch helper in lib/api.ts must go through ENDPOINTS (no stray literals)."""
    text = (WEB_SOTA_SRC / "lib" / "api.ts").read_text(encoding="utf-8")
    # The ENDPOINTS map itself holds literals by design - scan everything else.
    block_start = text.find("export const ENDPOINTS")
    block_end = text.find("} as const", block_start)
    assert block_start != -1 and block_end != -1, "ENDPOINTS map not found"
    text = text[:block_start] + text[block_end:]
    strays = []
    for m in _LITERAL_RE.finditer(text):
        route = _strip(m.group(1))
        if route:
            strays.append(route)
    assert not strays, f"lib/api.ts inlines route literals outside ENDPOINTS: {strays}"
