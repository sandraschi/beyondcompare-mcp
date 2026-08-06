#!/usr/bin/env python3
"""Test script to validate pyproject.toml syntax and dependencies."""

import sys

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Python 3.10 fallback


def test_toml_syntax():
    """Test if pyproject.toml has valid syntax."""
    try:
        with open("pyproject.toml", "rb") as f:
            tomllib.load(f)
        print("✅ pyproject.toml syntax is valid")
        return True
    except Exception as e:
        print(f"❌ pyproject.toml syntax error: {e}")
        return False


def test_imports():
    """Test if all required imports work."""
    results = []

    # Test FastMCP import
    try:
        from fastmcp import FastMCP

        print("✅ FastMCP import successful")
        results.append(True)
    except ImportError as e:
        print(f"❌ FastMCP import failed: {e}")
        results.append(False)

    # Test MCP SDK import
    try:
        import mcp

        print("✅ MCP SDK import successful")
        results.append(True)
    except ImportError as e:
        print(f"❌ MCP SDK import failed: {e}")
        results.append(False)

    # Test other dependencies
    other_imports = [
        ("pydantic", "Pydantic import"),
        ("dotenv", "python-dotenv import"),
        ("anyio", "AnyIO import"),
        ("structlog", "Structlog import"),
    ]

    for module, description in other_imports:
        try:
            __import__(module)
            print(f"✅ {description} successful")
            results.append(True)
        except ImportError as e:
            print(f"❌ {description} failed: {e}")
            results.append(False)

    return all(results)


def test_project_imports():
    """Test if project-specific imports work."""
    try:
        sys.path.insert(0, "src")
        from beyondcompare_mcp import __version__

        print(f"✅ Project version import successful: {__version__}")
        return True
    except ImportError as e:
        print(f"❌ Project version import failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🔍 Testing Beyond Compare MCP project setup...\n")

    results = []

    print("1. Testing TOML syntax...")
    results.append(test_toml_syntax())

    print("\n2. Testing dependency imports...")
    results.append(test_imports())

    print("\n3. Testing project imports...")
    results.append(test_project_imports())

    print("\n" + "=" * 50)
    if all(results):
        print("🎉 All tests passed! Project setup is working.")
        return 0
    else:
        print("💥 Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
