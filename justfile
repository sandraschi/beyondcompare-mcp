set windows-shell := ["powershell.exe", "-NoProfile", "-Command"]
import 'scripts/just/fleet.just'

# Open the interactive recipe dashboard in the browser
default:
    @just --list

# --- Quality ---

# Execute Ruff SOTA v13.1 linting (same scope as CI)
lint:
    Set-Location '{{justfile_directory()}}'; uv run ruff check src/ tests/ scripts/; Set-Location '{{justfile_directory()}}\web_sota'; npx @biomejs/biome ci .

# Execute Ruff SOTA v13.1 fix and formatting
fix:
    Set-Location '{{justfile_directory()}}'; uv run ruff check src/ tests/ scripts/ --fix --unsafe-fixes; uv run ruff format src/ tests/ scripts/; Set-Location '{{justfile_directory()}}\web_sota'; npx @biomejs/biome check --write .

# --- Tests ---

# Run pytest (excludes heavy integration suite)
test:
    Set-Location '{{justfile_directory()}}'; uv sync --extra dev; uv run python -m pytest tests -q --ignore=tests/test_integration.py

# --- Serve ---

# Start the backend gateway only (frontend: cd web_sota; npm run dev)
serve:
    Set-Location '{{justfile_directory()}}'; powershell.exe -NoProfile -File "{{justfile_directory()}}\start.ps1" -BackendOnly

# --- Format ---

# Check formatting without writing (CI gate)
fmt-check:
    Set-Location '{{justfile_directory()}}'; uv run ruff format . --check

# --- CI ---

# Local gates (same scope as CI): lint + format check + tests
ci:
    Set-Location '{{justfile_directory()}}'; uv run ruff check src/ tests/ scripts/; uv run ruff format src/ tests/ scripts/ --check; uv run python -m pytest tests -q --ignore=tests/test_integration.py

# --- Native (Tauri NSIS) ---

# Full NSIS build: tsc + PyInstaller backend + Tauri bundle (needs cargo + NSIS)
build-native:
    Set-Location '{{justfile_directory()}}'; powershell.exe -NoProfile -File "{{justfile_directory()}}\native\build.ps1"

# --- Hardening ---

# Execute Bandit security audit
check-sec:
    Set-Location '{{justfile_directory()}}'; uv run bandit -r src/

# Execute safety audit of dependencies
audit-deps:
    Set-Location '{{justfile_directory()}}'; uv run safety check


# Bootstrap: install dev deps + pre-commit hook
bootstrap:
    Set-Location '{{justfile_directory()}}'; uv sync --group dev; uv run pre-commit install; Write-Host "Pre-commit hooks installed." -ForegroundColor Green
