#!/usr/bin/env python3
"""Test FastMCP import and basic functionality."""


def test_fastmcp_import():
    """Test different ways to import FastMCP."""
    print("Testing FastMCP import methods...")

    # Method 1: Direct import
    try:
        from fastmcp import FastMCP

        print("✅ Direct import: from fastmcp import FastMCP")
        return True
    except ImportError as e:
        print(f"❌ Direct import failed: {e}")

    # Method 2: Module import
    try:
        import fastmcp

        FastMCP = fastmcp.FastMCP
        print("✅ Module import: import fastmcp; fastmcp.FastMCP")
        return True
    except (ImportError, AttributeError) as e:
        print(f"❌ Module import failed: {e}")

    # Method 3: Server import
    try:
        from fastmcp.server import FastMCP

        print("✅ Server import: from fastmcp.server import FastMCP")
        return True
    except ImportError as e:
        print(f"❌ Server import failed: {e}")

    # Method 4: Check what's available
    try:
        import fastmcp

        print(f"FastMCP module contents: {dir(fastmcp)}")
        return False
    except ImportError as e:
        print(f"❌ FastMCP not available at all: {e}")
        return False


def test_mcp_import():
    """Test MCP SDK import."""
    print("\nTesting MCP SDK import...")

    try:
        import mcp

        print(f"✅ MCP import successful, contents: {dir(mcp)}")
        return True
    except ImportError as e:
        print(f"❌ MCP import failed: {e}")
        return False


def main():
    """Run import tests."""
    print("🔍 Testing MCP-related imports...\n")

    fastmcp_ok = test_fastmcp_import()
    mcp_ok = test_mcp_import()

    print("\n" + "=" * 50)
    if fastmcp_ok and mcp_ok:
        print("🎉 All MCP imports working!")
    else:
        print("⚠️  Some imports failed - need to fix dependencies")

    return 0 if (fastmcp_ok and mcp_ok) else 1


if __name__ == "__main__":
    exit(main())
