#!/usr/bin/env python3
"""CUA smoke test for NSIS-installed fleet apps (pywinauto-mcp canary).

CUA_SMOKE_VERSION = 13
If this file differs from templates/tauri-native/scripts/cua-smoke.py in
mcp-central-docs, copy the template over - version number will have changed.

Usage:
    python scripts/cua-smoke.py
    python scripts/cua-smoke.py --installer path/to/setup.exe
    python scripts/cua-smoke.py --config scripts/cua-nsis-config.json

Phases (implemented):
    1. Kill stale processes
    2. Silent install NSIS
    3. Launch app, wait for backend health
    4. Verify window (pywinauto)
    5. Screenshot evidence
    6. Feature-route smoke (health + data endpoint)
    7. Check diagnostics
    8. WebView bridge proof (OCR)
    9. Uninstall
    10. Report pass/fail

Phases (planned Phase 3): nav sidebar click-through, floating chat visibility.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

try:
    import tkinter as _tk

    _HAS_TK = True
except ImportError:
    _tk = None  # type: ignore[assignment]
    _HAS_TK = False

# ── Config ────────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cua-nsis-config.json")


def load_config(path: str | None = None) -> dict:
    p = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(p):
        print(f"  [cua] WARNING: config not found at {p}, using built-in defaults", flush=True)
        return {}
    with open(p) as f:
        cfg = json.load(f)

    # Expand env vars in string values
    def _expand(v):
        if isinstance(v, str):
            return os.path.expandvars(v)
        if isinstance(v, list):
            return [_expand(x) for x in v]
        return v

    return {k: _expand(v) for k, v in cfg.items()}


CUA_SMOKE_VERSION = 13  # bump when template changes; see docstring


def _check_version():
    """Warn if this file doesn't match the template version."""
    from pathlib import Path

    # If the template path exists, compare versions
    tpl = Path(os.getenv("MCP_CENTRAL_DOCS", "")) / "templates/tauri-native/scripts/cua-smoke.py"
    if tpl.exists():
        tpl_text = tpl.read_text(encoding="utf-8")
        import re

        m = re.search(r"CUA_SMOKE_VERSION\s*=\s*(\d+)", tpl_text)
        if m and int(m.group(1)) > CUA_SMOKE_VERSION:
            print(
                f"  [cua] WARNING: cua-smoke.py v{CUA_SMOKE_VERSION} is outdated "
                f"(template v{m.group(1)}). Copy template over.",
                flush=True,
            )


def cfg(key: str, default=""):
    return _CONFIG.get(key, default)


_CONFIG = load_config()

# ── Derived constants ─────────────────────────────────────────────────

BACKEND_PORT = int(cfg("backend_port", 10789))
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
PRODUCT_NAME = cfg("product_name", "Pywinauto MCP Operator")
HEALTH_PATH = cfg("health_path", "/api/v1/health")
DIAGNOSTICS_PATH = cfg("diagnostics_path", "/api/v1/diagnostics")
FEATURE_PATH = cfg("feature_smoke_path", "/api/v1/system/info")
REQUEST_LOG_PATH = cfg("request_log_path", "/api/v1/request-log")
WINDOW_TITLE_RE = cfg("window_title_re", "Pywinauto MCP")
BRIDGE_OK_TEXT = cfg("bridge_ok_text", "REST bridge reachable")
INSTALL_DIR = cfg("install_dir", "%LOCALAPPDATA%\\Pywinauto MCP Operator")
OPERATOR_EXE = cfg("operator_exe", "pywinauto-mcp-operator.exe")
PROCESS_NAMES = cfg("backend_process_names", ["pywinauto-mcp-operator", "pywinauto-mcp-backend"])
NSIS_GLOB = cfg("nsis_glob", "web_sota/src-tauri/target/release/bundle/nsis/Pywinauto MCP Operator_*_x64-setup.exe")
REGISTRY_FILTER = cfg("uninstall_registry_filter", "*Pywinauto*")
# 60s budget: a freshly-installed PyInstaller onefile backend exe triggers a
# fresh Windows Defender real-time scan on top of onefile self-extraction to
# %TEMP%\_MEI*, measured ~35-40s cold; the old 30s budget declared FATAL
# while the backend was still healthy (see TRAPS_AND_PITFALLS.md).
MAX_RETRY = 20
RETRY_DELAY = 3

_INSTALLED = False


# ── Helpers (must be before CUA client) ────────────────────────────


def log(msg: str):
    print(f"  [cua] {msg}", flush=True)


def log_warn(msg: str):
    print(f"  [WARN] {msg}", flush=True)


def http_get(url: str, timeout: int = 5):
    """GET with http/https scheme enforcement (S310: never file:/custom schemes)."""
    from urllib.parse import urlparse as _urlparse

    target = url.full_url if isinstance(url, urllib.request.Request) else url
    if _urlparse(target).scheme not in ("http", "https"):
        raise ValueError(f"refusing non-http URL: {target}")
    return urllib.request.urlopen(url, timeout=timeout)  # noqa: S310 - scheme validated above, localhost smoke only


# ── Direct pywinauto (no pywinauto-mcp dependency) ─────────────────

try:
    import pywinauto
    import pywinauto.findwindows

    _HAS_PYWAUTO = True
except ImportError:
    _HAS_PYWAUTO = False


def cua_available() -> bool:
    return _HAS_PYWAUTO


def _find_tauri_window(title_re: str):
    """Find Tauri webview window - excludes classic apps by class_name."""
    wins = pywinauto.findwindows.find_elements(title_re=title_re)
    tauri = [w for w in wins if w.class_name != "QMainWindow"]
    if not tauri:
        raise RuntimeError(f"No Tauri window found (classes: {set(w.class_name for w in wins)})")
    return tauri[0].handle


def _get_window(handle: int):
    app = pywinauto.Application(backend="uia").connect(handle=handle)
    return app.window(handle=handle)


def cua_find_window(title_re: str = "", retry_seconds: int = 10) -> dict | None:
    """Find a window by title regex. Returns {handle, title, rect} or None.

    Retries for up to `retry_seconds` (1s poll) - the backend can report
    healthy before the WebView2 window has finished initializing and
    rendering, so a single immediate lookup right after the health check
    is a common false-negative source (window genuinely appears a couple
    seconds later).
    """
    import pywinauto

    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            wins = pywinauto.findwindows.find_elements(title_re=title_re)
            tauri = [w for w in wins if w.class_name != "QMainWindow"]
            if tauri:
                handle = tauri[0].handle
                app = pywinauto.Application(backend="uia").connect(handle=handle)
                win = app.window(handle=handle)
                win.wait("visible", timeout=5)
                rect = win.rectangle()
                w = rect.width if isinstance(rect.width, int) else rect.width()
                h = rect.height if isinstance(rect.height, int) else rect.height()
                return {
                    "handle": handle,
                    "title": win.window_text(),
                    "rect": {"left": rect.left, "top": rect.top, "width": w, "height": h},
                }
        except Exception as e:
            log_warn(f"window probe retry: {e}")
        if time.monotonic() >= deadline:
            return None
        time.sleep(1)


def cua_screenshot(window_handle: int = 0, output_path: str = "") -> str | None:
    """Take a screenshot. Returns path or None."""
    try:
        import pywinauto

        wins = pywinauto.findwindows.find_elements(title_re=WINDOW_TITLE_RE)
        tauri = [w for w in wins if w.class_name != "QMainWindow"]
        if tauri:
            app = pywinauto.Application(backend="uia").connect(handle=tauri[0].handle)
            win = app.window(handle=tauri[0].handle)
            capture = win.capture_as_image()
            capture.save(output_path)
            return output_path
    except Exception as e:
        log_warn(f"screenshot failed: {e}")
        return None


def _show_automation_warning():
    """Warn user that automation is about to click around. Flashes a red HUD overlay."""
    print("\n  " + "!" * 60, flush=True)
    print("  !!! CUA AUTOMATION WARNING !!!", flush=True)
    print("  !!! The script will now take control of the mouse and keyboard.", flush=True)
    print("  !!! Please do not touch the mouse or keyboard until the test completes.", flush=True)
    print("  !!! This will take approximately 3 seconds per page.", flush=True)
    print("  " + "!" * 60 + "\n", flush=True)
    time.sleep(3)


class StopRequested(Exception):
    """Raised when the user hits the on-screen emergency STOP."""


_stop_event = threading.Event()
_go_event = threading.Event()
_aborted_before_start = {"value": False}


def _overlay_thread_main(countdown_seconds: int) -> None:
    """On-screen safety UI (runs in a daemon thread).

    Phase A: blocking red countdown dialog with an Abort button. The main
    thread waits for it before touching anything; Abort exits pre-install.
    Phase B: tiny always-on-top red banner with a STOP button for the whole
    run. STOP sets _stop_event; test phases check it and unwind to uninstall.
    The banner is a separate top-level window, so per-window screenshots
    (PrintWindow captures) never contain it.
    """
    assert _tk is not None
    try:
        root = _tk.Tk()
    except Exception as e:
        log_warn(f"overlay: Tk failed ({e}) - running without on-screen safety UI")
        _go_event.set()
        return
    root.withdraw()

    # ── Phase A: countdown dialog ──
    remaining = {"n": max(int(countdown_seconds), 0)}

    def _abort():
        _aborted_before_start["value"] = True
        _stop_event.set()
        _go_event.set()
        try:
            dialog.destroy()
        except Exception as e:
            log_warn(f"overlay abort destroy failed: {e}")

    def _tick():
        if _aborted_before_start["value"]:
            return
        if remaining["n"] <= 0:
            try:
                dialog.destroy()
            except Exception as e:
                log_warn(f"overlay countdown destroy failed: {e}")
            _go_event.set()
            _show_banner(root)
            return
        count_var.set(f"Starting in {remaining['n']} s - do not touch mouse/keyboard")
        remaining["n"] -= 1
        dialog.after(1000, _tick)

    if remaining["n"] <= 0:
        _go_event.set()
        _show_banner(root)
        root.mainloop()
        return

    dialog = _tk.Toplevel(root)
    dialog.title("CUA automation test")
    dialog.attributes("-topmost", True)
    dialog.resizable(False, False)
    dialog.configure(bg="#7f1d1d")
    _center(dialog, 420, 200)
    _tk.Label(
        dialog,
        text="CUA AUTOMATION TEST\nBeyond Compare MCP",
        font=("Segoe UI", 13, "bold"),
        fg="white",
        bg="#7f1d1d",
    ).pack(pady=(14, 4))
    count_var = _tk.StringVar(value="")
    _tk.Label(dialog, textvariable=count_var, font=("Segoe UI", 10), fg="#fecaca", bg="#7f1d1d").pack(pady=4)
    _tk.Button(
        dialog,
        text="ABORT TEST",
        font=("Segoe UI", 11, "bold"),
        fg="white",
        bg="#dc2626",
        activebackground="#991b1b",
        command=_abort,
        padx=18,
        pady=6,
    ).pack(pady=10)
    dialog.after(200, _tick)
    root.mainloop()


def _center(win, w: int, h: int) -> None:
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    except Exception as e:
        log_warn(f"overlay center failed: {e}")


def _show_banner(root) -> None:
    """Tiny always-on-top red banner with emergency STOP. Self-destroys on stop."""
    banner = _tk.Toplevel(root)
    banner.title("CUA running")
    banner.attributes("-topmost", True)
    banner.overrideredirect(True)
    banner.configure(bg="#dc2626")
    try:
        sw = banner.winfo_screenwidth()
        sh = banner.winfo_screenheight()
        banner.geometry(f"216x64+{sw - 232}+{sh - 140}")
    except Exception as e:
        log_warn(f"overlay banner geometry failed: {e}")

    def _stop():
        _stop_event.set()
        try:
            banner.destroy()
        except Exception as e:
            log_warn(f"overlay stop destroy failed: {e}")

    _tk.Label(banner, text="CUA TEST RUNNING", font=("Segoe UI", 9, "bold"), fg="white", bg="#dc2626").pack(pady=(6, 0))
    _tk.Button(
        banner,
        text="STOP",
        font=("Segoe UI", 10, "bold"),
        fg="#dc2626",
        bg="white",
        activebackground="#fecaca",
        command=_stop,
        padx=24,
    ).pack(pady=4)

    def _poll():
        if _stop_event.is_set():
            try:
                banner.destroy()
            except Exception as e:
                log_warn(f"overlay poll destroy failed: {e}")
            return
        try:
            banner.after(500, _poll)
        except Exception as e:
            log_warn(f"overlay poll reschedule failed: {e}")

    banner.after(500, _poll)


def start_safety_overlay(countdown_seconds: int = 15) -> bool:
    """Show the on-screen warning; block until countdown elapsed or aborted.

    Returns True when the run may proceed, False when the user aborted
    (caller must exit before installing anything).
    """
    if not _HAS_TK:
        log_warn("overlay: tkinter unavailable - no on-screen warning or STOP button")
        _go_event.set()
        return True
    t = threading.Thread(target=_overlay_thread_main, args=(countdown_seconds,), daemon=True)
    t.start()
    _go_event.wait(timeout=max(int(countdown_seconds), 0) + 30)
    if _aborted_before_start["value"]:
        log("Run aborted by user at the pre-start warning - nothing was installed")
        return False
    return True


def stop_safety_overlay() -> None:
    """Signal run end so the banner destroys itself."""
    _stop_event.set()


def check_stop() -> None:
    """Raise StopRequested when the user hit emergency STOP."""
    if _stop_event.is_set():
        raise StopRequested("emergency STOP pressed at the PC")


def cua_ocr_text(window_handle: int = 0, image_path: str = "") -> str:
    """Run OCR on a window screenshot. Returns text."""
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if image_path and os.path.exists(image_path):
            from PIL import Image

            return pytesseract.image_to_string(Image.open(image_path))
        if window_handle:
            from PIL import Image

            capture = cua_screenshot(window_handle, f"{image_path or 'capture'}.png")
            if capture and os.path.exists(capture):
                return pytesseract.image_to_string(Image.open(capture))
    except Exception as e:
        log_warn(f"OCR failed: {e}")
    return ""


def cua_click(window_handle: int, x: int, y: int):
    """Click at (x,y) relative to window."""
    try:
        import pywinauto.mouse

        pywinauto.mouse.click(button="left", coords=(x, y))
    except Exception as e:
        log_warn(f"click at {(x, y)} failed: {e}")


def _release_mouse():
    """Release the left button and dismiss any stray menu - call before and
    after clicking. Deliberately sends LEFTUP ONLY: a bare RIGHTUP with no
    preceding RIGHTDOWN makes Windows fire WM_CONTEXTMENU at the cursor,
    which opened Chromium context menus over the sidebar on every nav step
    (screenshots showed link/page menus instead of navigation), and a bare
    MIDDLEUP can trigger autoscroll. LEFTUP without a preceding DOWN is a
    harmless no-op. Escape dismisses any menu that is already open."""
    try:
        import ctypes

        MOUSEEVENTF_LEFTUP = 0x0004
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    except Exception as e:
        log_warn(f"mouse-button release failed: {e}")
    try:
        import ctypes
        import time as _time

        VK_ESCAPE = 0x1B
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        _time.sleep(0.5)
    except Exception as e:
        log_warn(f"escape key release failed: {e}")


# ── Helpers ───────────────────────────────────────────────────────────


class PhaseFailed(Exception):
    """Non-fatal phase failure - script continues to uninstall."""


def fatal(msg: str):
    print(f"  [cua] FATAL: {msg}", flush=True)
    sys.exit(1)


def phase_fail(msg: str):
    print(f"  [cua] PHASE FAIL: {msg}", flush=True)
    raise PhaseFailed(msg)


# ── Phase 1: Kill stale ───────────────────────────────────────────────


def kill_stale():
    for name in PROCESS_NAMES:
        subprocess.run(["taskkill", "/F", "/IM", f"{name}.exe", "/T"], capture_output=True, timeout=10)
    time.sleep(1)
    log("Stale processes killed")


# ── Phase 2: Install ──────────────────────────────────────────────────


def find_installer() -> str:
    import glob

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(repo_root, *NSIS_GLOB.replace("/", "\\").split("\\"))
    matches = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if matches:
        return matches[0]
    fatal("No NSIS installer found. Run 'just build-native' first.")


def silent_install(installer: str):
    log(f"Installing: {installer}")
    r = subprocess.run([installer, "/S"], capture_output=True, timeout=120)
    if r.returncode != 0:
        fatal(f"NSIS install exited with code {r.returncode}")
    global _INSTALLED
    _INSTALLED = True
    time.sleep(2)
    log("Install complete")


# ── Phase 3: Launch ──────────────────────────────────────────────────


def launch_app():
    exe = os.path.join(INSTALL_DIR, OPERATOR_EXE)
    if not os.path.exists(exe):
        fatal(f"Operator not found at {exe}")
    env = os.environ.copy()
    env_vars = cfg("env_vars", {})
    if isinstance(env_vars, dict):
        for k, v in env_vars.items():
            env[k] = str(v)
            log(f"  Set env {k}={v}")
    subprocess.Popen([exe], cwd=INSTALL_DIR, env=env)
    log(f"Launched {exe}")
    for attempt in range(MAX_RETRY):
        try:
            resp = http_get(f"{BACKEND_URL}{HEALTH_PATH}", timeout=5)
            if resp.status == 200:
                log(f"Backend healthy (attempt {attempt + 1})")
                return
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass
        time.sleep(RETRY_DELAY)
    fatal(f"Backend not reachable after {MAX_RETRY * RETRY_DELAY}s")


# ── Phase 4: Verify window ───────────────────────────────────────────


def _foreground_and_maximize(handle: int):
    """Bring the app window to front and maximize it. MUST be called before every
    screenshot-based check (not just the nav walk) - capture_as_image()/PrintWindow
    on an unfocused/occluded WebView2 window can silently return whatever window
    IS on top instead of the target, since Chromium's compositor surface doesn't
    always reflect through PrintWindow the way a plain native window does when not
    foregrounded. Confirmed on kicad-mcp 2026-09-22: an OCR check without this
    captured unrelated desktop content (a notes window) instead of the app."""
    try:
        import pywinauto

        app = pywinauto.Application(backend="uia").connect(handle=handle)
        w = app.window(handle=handle)
        w.set_focus()
        w.maximize()
        time.sleep(1)
    except Exception as e:
        log_warn(f"window focus/maximize failed: {e}")


def verify_window():
    if not cua_available():
        log("CUA client unavailable -- window check skipped")
        return
    win = cua_find_window(WINDOW_TITLE_RE)
    if win:
        r = win.get("rect", {}) or {}
        w = r.get("width", 0) or 0
        h = r.get("height", 0) or 0
        log(f"Window '{win.get('title', '?')}' found: {w}x{h}")
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0 and (w < 100 or h < 100):
            phase_fail(f"Window too small: {w}x{h}")
        _foreground_and_maximize(win.get("handle", 0))
    else:
        log(f"Window matching '{WINDOW_TITLE_RE}' not found")


# ── Phase 5: Screenshot ──────────────────────────────────────────────


def take_screenshot(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    win = cua_find_window(WINDOW_TITLE_RE, retry_seconds=2)
    if win:
        _foreground_and_maximize(win.get("handle", 0))
    path = os.path.join(output_dir, f"cua-smoke-{int(time.time())}.png")
    result = cua_screenshot(0, path)
    if result and os.path.exists(result):
        log(f"Screenshot saved: {result} ({os.path.getsize(result)} bytes)")
    else:
        log("Screenshot not available (CUA client needed)")


# ── Phase 6: Feature-route smoke ─────────────────────────────────────


def check_feature_route():
    try:
        resp = http_get(f"{BACKEND_URL}{FEATURE_PATH}", timeout=5)
        body = json.loads(resp.read())
        log(f"Feature route {FEATURE_PATH}: HTTP {resp.status}")
        if resp.status == 200:
            log(f"  response keys: {list(body.keys())[:5]}")
    except Exception as e:
        log(f"Feature route check failed (non-fatal): {e}")


# ── Phase 7: Diagnostics ─────────────────────────────────────────────


def check_diagnostics():
    try:
        resp = http_get(f"{BACKEND_URL}{DIAGNOSTICS_PATH}", timeout=5)
        data = json.loads(resp.read())
        if data.get("success"):
            # Flat shape (this repo): backend/system/tools/cua_status at top level.
            d = data.get("data", data)
            backend = d.get("backend", {})
            log(f"Backend: {backend.get('status')} port={backend.get('port')} uptime={backend.get('uptime')}s")
            log(
                f"System: CPU {d.get('system', {}).get('cpu_percent')}% | Mem {d.get('system', {}).get('memory_percent')}% | Disk {d.get('system', {}).get('disk_percent')}%"
            )
            log(f"Tools: {d.get('tools', {}).get('total')} registered")
            log(
                f"CUA: Tesseract={d.get('cua_status', {}).get('tesseract_available')} Window={d.get('cua_status', {}).get('window_found')}"
            )
            if d.get("errors", {}).get("count", 0) > 0:
                log(f"WARNING: {d['errors']['count']} errors logged")
        else:
            log(f"Diagnostics returned: {data}")
    except Exception as e:
        log(f"Diagnostics check failed (non-fatal): {e}")


# ── Phase 8: WebView bridge proof (OCR) ──────────────────────────────


def verify_webview_bridge(output_dir: str):
    if not cua_available():
        log("CUA client unavailable -- WebView bridge check skipped")
        return
    os.makedirs(output_dir, exist_ok=True)
    # Retry with delay: the frontend's OWN health poll (independent of the backend
    # being reachable, which was already confirmed in Phase 3) uses exponential
    # backoff (1s, 2s, 4s, 8s, 16s, 30s per the connection-health standard). If its
    # first attempt landed before the backend finished binding, a single-shot check
    # right after Phase 6/7 can catch it mid-backoff and false-fail a healthy app
    # (kicad-mcp, 2026-09-22: confirmed "System Online" appears fine given ~15-20s).
    text = ""
    for attempt in range(6):
        check_stop()
        win = cua_find_window(WINDOW_TITLE_RE, retry_seconds=2)
        if win:
            _foreground_and_maximize(win.get("handle", 0))
        snap_path = os.path.join(output_dir, f"bridge-snap-{int(time.time())}.png")
        result = cua_screenshot(0, snap_path)
        text = cua_ocr_text(0, snap_path or "")
        if not text and result and os.path.exists(snap_path):
            text = cua_ocr_text(image_path=snap_path)
        if BRIDGE_OK_TEXT.lower() in text.lower() or "connected" in text.lower():
            log(f"WebView bridge OK (found '{BRIDGE_OK_TEXT}' in screenshot OCR, attempt {attempt + 1})")
            return
        if attempt < 5:
            time.sleep(5)
    if text:
        log(f"WebView OCR text: {text[:200]}")
        phase_fail(f"WebView bridge not OK - likely API_BASE/CSP/CORS (expected '{BRIDGE_OK_TEXT}')")
    else:
        log("WebView bridge check skipped (no OCR available)")


# ── Phase 9: Nav click-through ──────────────────────────────────────


def _verify_page_ocr(text: str, label: str, expected: str) -> bool:
    """Check OCR text for page validity. Returns True if page seems OK."""
    text_lower = text.lower()
    # Bare "error"/"timeout"/"not found" are too broad: legitimate pages describe
    # error-handling behavior, show log entries with an ERROR level, have a
    # "Timeout (s)" settings field, or show a genuine "Service: Not found" status
    # for an optional integration that simply isn't running (found via
    # teleoperator-mcp's Inbox page false-positiving on "Warnings and errors are
    # surfaced" descriptive text, and browser-mcp's Settings page false-positiving
    # on "Vllm :8000 Not found" -- a correct, expected status, not an error).
    # Use specific failure phrases instead.
    fail_keywords = [
        "404",
        "page not found",
        "resource not found",
        "could not find",
        "internal server error",
        "bad gateway",
        "unexpected error",
        "an error occurred",
        "application error",
        "failed to load",
        "connection timed out",
        "request timed out",
    ]
    for kw in fail_keywords:
        if kw in text_lower:
            log(f"  Page '{label}': ERROR keyword '{kw}' found in OCR")
            return False
    if not text.strip():
        log(f"  Page '{label}': EMPTY OCR - page may be blank or not loading")
        return False
    if expected.lower() in text_lower:
        log(f"  Page '{label}': V OK (found '{expected}')")
        return True
    log(f"  Page '{label}': X expected '{expected}' not found in OCR - page may be wrong")
    return False


def _history_back() -> None:
    """Send Alt+Left (WebView2 history-back accelerator) to leave a dead page."""
    try:
        import ctypes
        import time as _time

        VK_MENU = 0x12
        VK_LEFT = 0x25
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(VK_MENU, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_LEFT, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_LEFT, 0, KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        _time.sleep(2)
    except Exception as e:
        log_warn(f"history-back failed: {e}")


def _nav_click_element(win_handle: int, wx: int, wy: int, idx: int, label: str = "", skip_tree: bool = False):
    """Click a nav item. Tries title-based UIA matching first, then index, then coordinates.

    skip_tree: when the renderer is suspected dead (previous page crashed),
    UIA tree queries can hang or return garbage - go straight to the
    calibrated coordinate fallback.
    """
    import pywinauto

    if skip_tree:
        log(f"nav '{label}': skipping tree queries (renderer suspected dead)")
    else:
        app = pywinauto.Application(backend="uia").connect(handle=win_handle)
        w = app.window(handle=win_handle)

        # Preferred: match by accessible name (title= is the pywinauto criteria for UIA Name).
        # Index-based Hyperlink ordering is fragile - sidebar order may differ from nav_routes.
        if label:
            try:
                link = w.descendants(title=label)
                if link:
                    log(f"nav '{label}': title-match ({len(link)} hits)")
                    link[0].click_input()
                    return
            except Exception as e:
                log_warn(f"title-match nav failed for {label!r}: {e}")
            try:
                elements = w.descendants(control_type="Hyperlink")
                el = [e for e in elements if label.lower() in (e.window_text() or "").lower()]
                if el:
                    log(f"nav '{label}': hyperlink-match")
                    el[0].click_input()
                    return
            except Exception as e:
                log_warn(f"hyperlink nav failed for {label!r}: {e}")

        # Fallback: positional Hyperlink
        try:
            elements = w.descendants(control_type="Hyperlink")
            if idx < len(elements):
                log(f"nav '{label}': positional hyperlink {idx}")
                elements[idx].click_input()
                return
        except Exception as e:
            log_warn(f"positional hyperlink nav failed: {e}")
        # Try Pane (some WebView versions)
        try:
            elements = w.descendants(control_type="Pane")
            nav_elements = [e for e in elements if e.rectangle().left < wx + 200]
            nav_elements_sorted = sorted(nav_elements, key=lambda e: e.rectangle().top)
            if idx < len(nav_elements_sorted):
                log(f"nav '{label}': pane fallback {idx}")
                nav_elements_sorted[idx].click_input()
                return
        except Exception as e:
            log_warn(f"pane nav failed: {e}")

    # Fallback to coordinate click
    click_x = wx + int(cfg("sidebar_click_x", 30))
    click_y = wy + int(cfg("sidebar_first_y", 90)) + idx * int(cfg("sidebar_step_y", 55))
    log(f"nav '{label}': coordinate fallback ({click_x}, {click_y})")
    cua_click(win_handle, click_x, click_y)


def wait_for_dashboard_online(handle: int, output_dir: str, timeout_seconds: int = 120) -> bool:
    """Wait until the dashboard shows live data before any clicking.

    The frontend polls the backend on its own interval, so a healthy backend
    does NOT mean rendered KPIs yet. Polls screenshots for the "online" KPI
    text; returns True when seen, False on timeout (caller logs and continues -
    per-page results will show the truth).
    """
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    while time.monotonic() < deadline:
        check_stop()
        attempt += 1
        snap_path = os.path.join(output_dir, f"online-wait-{int(time.time())}.png")
        try:
            cua_screenshot(handle, snap_path)
            text = cua_ocr_text(handle, snap_path)
        except Exception as e:
            log_warn(f"online-wait snap failed: {e}")
            text = ""
        if "online" in text.lower():
            log(f"Dashboard online confirmed (attempt {attempt}) - KPIs live, starting clicks")
            return True
        log(f"Dashboard not online yet (attempt {attempt}) - waiting for badge + KPIs")
        time.sleep(5)
    log("Dashboard online NOT seen within timeout - proceeding anyway, per-page results decide")
    return False


def nav_click_through(output_dir: str):
    """Click each sidebar nav item, verify page loads via OCR."""
    if not cua_available():
        log("CUA client unavailable -- nav click-through skipped")
        return
    _release_mouse()
    _show_automation_warning()

    nav_routes = cfg(
        "nav_routes",
        [["Dashboard", "Automation Dashboard"], ["Logging", "Logs"], ["Settings", "Settings"], ["Help", "Help"]],
    )
    nav_routes = [(r[0], r[1]) for r in nav_routes if len(r) >= 2]
    win = cua_find_window(WINDOW_TITLE_RE)
    if not win:
        log("No window found for nav click-through")
        return
    handle = win.get("handle", 0)

    _foreground_and_maximize(handle)

    # Re-read the rect AFTER maximizing: the pre-maximize rect is stale and
    # every coordinate-fallback click would otherwise land in the wrong place.
    win = cua_find_window(WINDOW_TITLE_RE)
    if not win:
        log("Window lost after maximize - aborting nav click-through")
        return
    r = win.get("rect", {}) or {}
    wx = r.get("left", 0) or 0
    wy = r.get("top", 0) or 0
    handle = win.get("handle", 0)
    snap_dir = os.path.join(output_dir, "nav")

    wait_for_dashboard_online(handle, output_dir)

    crashed_pages: list[str] = []
    tree_dead = False
    for idx, (label, expected_header) in enumerate(nav_routes):
        check_stop()
        try:
            # Dismiss any stale menu first: an open menu swallows the click
            # (menu dismissal eats it) and the navigation silently never happens.
            _release_mouse()
            _nav_click_element(handle, wx, wy, idx, label, skip_tree=tree_dead)
            _release_mouse()
            time.sleep(3)

            snap_path = os.path.join(snap_dir, f"nav-{label.lower()}-{int(time.time())}.png")
            os.makedirs(snap_dir, exist_ok=True)
            cua_screenshot(handle, snap_path)
            text = cua_ocr_text(handle, snap_path)
            # Empty OCR after a settle wait means a black/blank renderer, not
            # a slow load - re-shot once to be sure before calling it crashed.
            if not text.strip():
                time.sleep(5)
                cua_screenshot(handle, snap_path)
                text = cua_ocr_text(handle, snap_path)

            ok = _verify_page_ocr(text, label, expected_header)
            if not text.strip():
                log(f"  Page '{label}': CRASHED (blank render) - attempting recovery")
                crashed_pages.append(label)
                tree_dead = True
                # Recovery: history-back out of the dead page, then reset to
                # a known-good page (Overview via calibrated coordinates).
                # Either step may fail on a dead renderer - best effort.
                _history_back()
                _release_mouse()
                time.sleep(2)
                cua_screenshot(handle, snap_path)
                text = cua_ocr_text(handle, snap_path)
                if not text.strip():
                    log("  Recovery via history-back failed - clicking Overview")
                    cua_click(
                        handle,
                        wx + int(cfg("sidebar_click_x", 30)),
                        wy + int(cfg("sidebar_first_y", 90)),
                    )
                    _release_mouse()
                    time.sleep(3)
                    cua_screenshot(handle, snap_path)
                    text = cua_ocr_text(handle, snap_path)
                    if text.strip():
                        log("  Recovery via Overview click OK - continuing walk")
                        tree_dead = False
                    else:
                        log("  Recovery failed - renderer still blank, continuing walk")
                else:
                    log("  Recovery via history-back OK - continuing walk")
                    tree_dead = False
            elif not ok:
                # Wrong content but alive renderer - keep tree queries enabled.
                tree_dead = False
        except Exception as e:
            log(f"Nav '{label}' failed (non-fatal): {e}")
            _release_mouse()

    _release_mouse()
    if crashed_pages:
        phase_fail(f"nav click-through crashed on page(s): {', '.join(crashed_pages)}")


# ── Phase 9b: Backend-receipt proof (bypasses webview entirely) ─────────


def verify_backend_received_requests(baseline_count: int):
    """Prove the webview's own fetches actually reached the backend.

    OCR-based nav verification can pass even when EVERY webview fetch is
    silently failing -- a page's title renders via client-side routing
    regardless of whether its data call succeeded, so a page showing its own
    name in OCR proves nothing about connectivity. This phase queries the
    backend's own request log directly (a plain HTTP GET, immune to whatever
    might be blocking the webview's fetches -- e.g. AppContainer loopback
    isolation when the installed app was launched from within a sandboxed
    parent process) and checks whether the nav-walk actually generated new
    backend traffic. Requires the target repo's backend to implement
    GET {request_log_path} returning {"count": int, "requests": [...]} --
    if it 404s, this repo hasn't adopted the pattern yet; skip, don't fail.
    See mcp-central-docs HANDOVER.md 2026-09-20 for the incident this
    phase exists to catch (browser-mcp: zero webview requests ever landed,
    across every page, for an entire CUA run -- OCR nav-walk still said
    'ALL PHASES PASSED').
    """
    try:
        req = urllib.request.Request(f"{BACKEND_URL}{REQUEST_LOG_PATH}")  # noqa: S310 - http_get validates scheme, localhost smoke only
        with http_get(req, timeout=5) as resp:
            if resp.status == 404:
                log("Backend-receipt check skipped (repo has no request-log endpoint yet)")
                return
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log("Backend-receipt check skipped (repo has no request-log endpoint yet)")
            return
        raise
    except Exception as e:
        log(f"Backend-receipt check failed to query (non-fatal): {e}")
        return

    new_count = data.get("count", 0) - baseline_count
    nav_route_count = len(cfg("nav_routes", []))
    if new_count <= 0:
        phase_fail(
            f"Backend received ZERO new requests during nav click-through "
            f"({nav_route_count} pages visited). The webview's fetches are not "
            f"reaching the backend at all -- every page's OCR pass is a false "
            f"positive proving only that titles render, not that data loads."
        )
    elif new_count < nav_route_count:
        log_warn(
            f"Backend received only {new_count} new requests for {nav_route_count} "
            f"pages visited -- some pages' fetches may not be landing."
        )
    else:
        log(f"Backend-receipt OK: {new_count} requests logged during nav click-through")


def _get_request_log_count() -> int:
    try:
        req = urllib.request.Request(f"{BACKEND_URL}{REQUEST_LOG_PATH}")  # noqa: S310 - http_get validates scheme, localhost smoke only
        with http_get(req, timeout=5) as resp:
            return json.loads(resp.read().decode()).get("count", 0)
    except Exception as e:
        log_warn(f"request-log count probe failed: {e}")
        return 0


# ── Phase 10: Log analysis ────────────────────────────────────────────


def analyze_logs():
    """Read the Tauri app logs and report errors/warnings."""
    log_paths = [
        os.path.join(INSTALL_DIR, "pywinauto-mcp.log"),
        os.path.expandvars(r"%APPDATA%\com.sandraschi.pywinauto-mcp\logs\backend-spawn.log"),
    ]
    errors = []
    warnings = []

    for path in log_paths:
        if not os.path.exists(path):
            continue
        log(f"Analyzing log: {path} ({os.path.getsize(path)} bytes)")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if "ERROR" in stripped or "CRITICAL" in stripped:
                        errors.append(stripped)
                    elif "WARNING" in stripped or "WARN" in stripped:
                        warnings.append(stripped)
        except Exception as e:
            log(f"Could not read {path}: {e}")

    if errors:
        log(f"ERRORS FOUND ({len(errors)}):")
        for err in errors[:10]:
            log(f"  ! {err[:200]}")
    else:
        log("No errors found in logs")

    if warnings:
        log(f"Warnings: {len(warnings)}")
        for warn in warnings[:5]:
            log(f"  ? {warn[:200]}")

    if errors:
        phase_fail(f"{len(errors)} errors found in app logs")


# ── Phase 11: Uninstall ───────────────────────────────────────────────


def uninstall():
    uninstaller = os.path.join(INSTALL_DIR, "uninstall.exe")
    if not os.path.exists(uninstaller):
        if _INSTALLED:
            log(f"Uninstaller not found at {uninstaller}")
        return
    r = subprocess.run([uninstaller, "/S"], capture_output=True, timeout=60)
    log(f"Uninstaller exited with code {r.returncode}")
    time.sleep(2)
    remaining = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-ItemProperty 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue | Where-Object {{ $_.DisplayName -like '{REGISTRY_FILTER}' }}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if remaining.stdout.strip():
        log("WARNING: App may still be registered")
    else:
        log("Clean: app uninstalled")


# ── Main ──────────────────────────────────────────────────────────────


def main():
    # Self-check: warn if template version differs
    _check_version()

    parser = argparse.ArgumentParser(description="CUA-NSIS smoke test")
    parser.add_argument("--installer", help="Path to NSIS installer .exe")
    parser.add_argument("--config", help="Path to cua-nsis-config.json")
    parser.add_argument("--output-dir", default="cua-reports", help="Screenshot output directory")
    args = parser.parse_args()

    if args.config:
        _CONFIG.update(load_config(args.config))

    _nav_baseline = {"count": 0}

    def _capture_nav_baseline():
        _nav_baseline["count"] = _get_request_log_count()

    def _run_nav_and_capture_baseline():
        _capture_nav_baseline()
        nav_click_through(args.output_dir)

    phases = [
        (True, "Kill stale processes", lambda: kill_stale()),
        (True, "Install NSIS", lambda: silent_install(args.installer or find_installer())),
        (True, "Launch app", launch_app),
        (False, "Verify window", verify_window),
        (False, "Screenshot", lambda: take_screenshot(args.output_dir)),
        (False, "Feature route", check_feature_route),
        (False, "Check diagnostics", check_diagnostics),
        (False, "WebView bridge", lambda: verify_webview_bridge(args.output_dir)),
        (False, "Nav click-through", _run_nav_and_capture_baseline),
        (False, "Backend-receipt proof", lambda: verify_backend_received_requests(_nav_baseline["count"])),
        (False, "Analyze app logs", analyze_logs),
        (False, "Uninstall", uninstall),
    ]

    passed = failed = 0
    fatal_failed = False

    print(f"\n{'=' * 50}")
    print(f"  CUA Smoke Test - {PRODUCT_NAME}")
    print(f"{'=' * 50}\n")

    if not start_safety_overlay(int(cfg("pre_warning_seconds", 15))):
        return

    if not _HAS_PYWAUTO:
        print("  !!! WARNING: pywinauto is not importable in this venv. !!!")
        print("  !!! Every GUI-driven phase will be SILENTLY SKIPPED.   !!!")
        print("  !!! Run: uv add --dev pywinauto pillow pytesseract     !!!")
        print("  !!! This run cannot verify the UI actually works.\n")

    try:
        for is_fatal, name, fn in phases:
            check_stop()
            print(f"  Phase {phases.index((is_fatal, name, fn)) + 1}: {name}")
            try:
                fn()
                print(f"  V {name}\n")
                passed += 1
            except StopRequested as e:
                print(f"  STOPPED {name}: {e} - unwinding to uninstall\n")
                failed += 1
                for _, uname, ufn in phases:
                    if uname == "Uninstall":
                        try:
                            ufn()
                            print("  V Uninstall (after STOP)\n")
                            passed += 1
                        except Exception as ue:
                            print(f"  X Uninstall (after STOP): {ue}\n")
                            failed += 1
                        break
                break
            except PhaseFailed:
                print(f"  X {name}\n")
                failed += 1
                if is_fatal:
                    fatal_failed = True
            except Exception as e:
                print(f"  X {name}: {e}\n")
                failed += 1
                if is_fatal:
                    fatal_failed = True
    finally:
        stop_safety_overlay()
        _release_mouse()

    print(f"{'=' * 50}")
    print(f"  Result: {passed}/{passed + failed} phases passed")
    if not _HAS_PYWAUTO:
        print("  WARNING: pywinauto was NOT importable in this venv - every GUI-driven")
        print("  phase (window verify, screenshot, WebView OCR, nav click-through) was")
        print("  SILENTLY SKIPPED, not verified. This run does NOT prove the UI works.")
        print("  Fix: add pywinauto, pillow, pytesseract as dev dependencies and re-run.")
    if failed:
        print(f"  {failed} phase(s) FAILED")
    if fatal_failed:
        print("  FATAL phase failure - see above")
        sys.exit(1)
    if failed or not _HAS_PYWAUTO:
        print("  NOT ALL PHASES PASSED - do not report this run as a clean pass")
        print(f"{'=' * 50}\n")
        sys.exit(1)
    print("  ALL PHASES PASSED")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
