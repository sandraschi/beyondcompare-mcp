"""
Beyond Compare MCP Server
========================

A modern MCP 2.11+ compliant server that provides file and directory comparison
capabilities using Beyond Compare. Built with security, reliability, and
performance in mind.

Features:
- File and folder comparison with Beyond Compare's powerful engine
- Directory synchronization with multiple sync modes
- Secure input validation and subprocess execution
- Modern MCP 2.11+ compliance
- Cross-platform support (Windows, macOS, Linux)
"""

# Version will be replaced during build
try:
    from ._version import __version__
except ImportError:
    __version__ = "0.1.0"  # fallback version

from .exceptions import (
    BeyondCompareCommandError,
    BeyondCompareError,
    BeyondCompareNotInstalledError,
    BeyondCompareScriptError,
    BeyondCompareTimeoutError,
)
from .server import BeyondCompareMCP

__all__ = [
    "BeyondCompareCommandError",
    "BeyondCompareError",
    "BeyondCompareMCP",
    "BeyondCompareNotInstalledError",
    "BeyondCompareScriptError",
    "BeyondCompareTimeoutError",
    "__version__",
]
