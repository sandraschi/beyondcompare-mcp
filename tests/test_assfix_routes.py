"""Assfix 2026-10-13: coverage for newly added gateway routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from beyondcompare_mcp.server import app, reset_fleet_stack_for_tests


def _client(tmp_path: Path) -> TestClient:
    reset_fleet_stack_for_tests()
    from beyondcompare_mcp.server import ensure_fleet_stack

    fake = tmp_path / "BCompare.exe"
    fake.write_bytes(b"\x00\x00")
    scripts = tmp_path / "bcscripts"
    scripts.mkdir(exist_ok=True)
    ensure_fleet_stack(bc_path=str(fake), scripts_dir=str(scripts))
    return TestClient(app)


def test_skills_endpoint(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/api/skills")
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert any(s["uri"] == "skill://beyondcompare-mcp/SKILL.md" for s in skills)


def test_fleet_apps_endpoint(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/api/fleet/apps")
    assert r.status_code == 200
    apps = r.json()["apps"]
    assert any(a["port"] == 10840 for a in apps)


def test_llm_standard_paths(tmp_path: Path) -> None:
    c = _client(tmp_path)
    for path in ("/api/llm/discover", "/api/llm/providers", "/api/llm/models", "/api/llm/onboarding"):
        r = c.get(path)
        assert r.status_code == 200, path
    disc = c.get("/api/llm/discover").json()
    assert "ollama" in disc and "lm_studio" in disc
    prov = c.get("/api/llm/providers").json()
    assert "ollama" in prov and "lm_studio" in prov


def test_llm_chat_routes_registered(tmp_path: Path) -> None:
    """Chat proxy routes exist (live LLM calls are verified manually, not in CI)."""
    reset_fleet_stack_for_tests()
    from beyondcompare_mcp.server import ensure_fleet_stack

    fake = tmp_path / "BCompare.exe"
    fake.write_bytes(b"\x00\x00")
    scripts = tmp_path / "bcscripts"
    scripts.mkdir(exist_ok=True)
    fapp, _, _ = ensure_fleet_stack(bc_path=str(fake), scripts_dir=str(scripts))
    paths = {getattr(r, "path", "") for r in fapp.routes}
    for p in ("/api/llm/chat", "/api/llm/chat/stream", "/api/shutdown", "/api/skills", "/api/fleet/apps"):
        assert p in paths, p


def test_logs_query_export_clear(tmp_path: Path) -> None:
    c = _client(tmp_path)
    # Seed one entry via a health call (middleware logs it).
    c.get("/api/v1/health")
    q = c.get("/api/logs?limit=10&sort=desc")
    assert q.status_code == 200
    assert "entries" in q.json() and "total" in q.json()
    v1 = c.get("/api/v1/logs?limit=5")
    assert v1.status_code == 200
    exp = c.get("/api/logs/export?format=csv")
    assert exp.status_code == 200
    assert "id,timestamp" in exp.text
    d = c.delete("/api/logs")
    assert d.json()["ok"] is True
    # The DELETE request itself appends one ring entry after clearing.
    assert c.get("/api/logs").json()["total"] == 1


def test_diagnostics_tool_count_live(tmp_path: Path) -> None:
    c = _client(tmp_path)
    d = c.get("/api/v1/diagnostics").json()
    assert d["tools"]["total"] >= 18
    assert "bc_status" in d["tools"]["names"]
