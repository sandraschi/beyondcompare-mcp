"""Main entry point for python -m beyondcompare_mcp execution."""

# CRITICAL: Set binary mode FIRST, before ANY other imports
# This is critical for Antigravity IDE compatibility
import os
import sys

if os.name == "nt":  # Windows
    try:
        import msvcrt

        # Set stdin/stdout to binary mode to prevent line ending conversion
        # This fixes "invalid trailing data" errors with Antigravity IDE
        try:
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        except (OSError, AttributeError):
            pass  # stdin might not be a real file descriptor
        try:
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except (OSError, AttributeError):
            pass  # stdout might not be a real file descriptor
    except (ImportError, OSError, AttributeError):
        pass  # If msvcrt is not available, continue anyway

# Set unbuffered mode
os.environ.setdefault("PYTHONUNBUFFERED", "1")

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
