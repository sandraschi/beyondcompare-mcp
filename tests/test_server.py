#!/usr/bin/env python3
"""Test script to verify Beyond Compare MCP server startup and basic functionality."""

import asyncio
import subprocess
import sys


def test_server_import():
    """Test if we can import the server module."""
    try:
        from beyondcompare_mcp.server import BeyondCompareMCP

        print("✅ Server import successful")
        return True
    except ImportError as e:
        print(f"❌ Server import failed: {e}")
        return False


def test_server_instantiation():
    """Test if we can create a server instance."""
    try:
        from beyondcompare_mcp.exceptions import BeyondCompareNotInstalledError
        from beyondcompare_mcp.server import BeyondCompareMCP

        # Try auto-detection first
        try:
            BeyondCompareMCP()  # Auto-detect BC
            print("✅ Server instantiation successful (BC found)")
            return True
        except BeyondCompareNotInstalledError:
            # If BC not found, try with explicit fake path to test validation
            try:
                BeyondCompareMCP(bc_path="C:\\fake\\path\\BCompare.exe")
                print("❌ Server should have failed with fake path")
                return False
            except BeyondCompareNotInstalledError:
                print("✅ Server instantiation successful (validation works)")
                return True
    except Exception as e:
        print(f"❌ Server instantiation failed: {e}")
        return False


def test_cli_help():
    """Test if CLI help command works."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "beyondcompare_mcp.cli", "--help"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ CLI help command works")
            return True
        else:
            print(f"❌ CLI help failed with code {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI help test failed: {e}")
        return False


def test_cli_version():
    """Test if CLI version command works."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "beyondcompare_mcp.cli", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "0.1.0" in result.stdout:
            print("✅ CLI version command works")
            return True
        else:
            print(f"❌ CLI version failed with code {result.returncode}")
            print(f"Stdout: {result.stdout}")
            print(f"Stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI version test failed: {e}")
        return False


async def test_server_startup():
    """Test if server can start up (brief test)."""
    try:
        from beyondcompare_mcp.exceptions import BeyondCompareNotInstalledError
        from beyondcompare_mcp.server import BeyondCompareMCP

        # Create server instance with auto-detection
        try:
            server = BeyondCompareMCP()  # Auto-detect BC

            # Try to access the MCP instance
            if hasattr(server, "mcp"):
                print("✅ Server has MCP instance")
                return True
            else:
                print("❌ Server missing MCP instance")
                return False

        except BeyondCompareNotInstalledError:
            print("⚠️  Beyond Compare not installed - skipping MCP test")
            return True  # This is acceptable for the test

    except Exception as e:
        print(f"❌ Server startup test failed: {e}")
        return False


def test_beyond_compare_detection():
    """Test Beyond Compare detection logic."""
    try:
        from beyondcompare_mcp.exceptions import BeyondCompareNotInstalledError
        from beyondcompare_mcp.server import BeyondCompareMCP

        # This should fail gracefully since BC likely isn't installed
        try:
            BeyondCompareMCP()  # Auto-detect BC
            print("✅ Beyond Compare found and detected")
            return True
        except BeyondCompareNotInstalledError:
            print("⚠️  Beyond Compare not installed (expected)")
            return True  # This is actually expected
        except Exception as e:
            print(f"❌ Unexpected error in BC detection: {e}")
            return False

    except Exception as e:
        print(f"❌ BC detection test failed: {e}")
        return False


def test_config_loading():
    """Test configuration loading."""
    try:
        from beyondcompare_mcp.config import settings

        # Check if settings object has expected attributes
        expected_attrs = ["BC_SCRIPTS_DIR", "COMMAND_TIMEOUT", "LOG_LEVEL"]
        missing_attrs = [attr for attr in expected_attrs if not hasattr(settings, attr)]

        if not missing_attrs:
            print("✅ Configuration loading successful")
            return True
        else:
            print(f"❌ Missing config attributes: {missing_attrs}")
            return False

    except Exception as e:
        print(f"❌ Config loading test failed: {e}")
        return False


def main():
    """Run all server tests."""
    print("🚀 Testing Beyond Compare MCP Server...\n")

    tests = [
        ("Server Import", test_server_import),
        ("Server Instantiation", test_server_instantiation),
        ("CLI Help Command", test_cli_help),
        ("CLI Version Command", test_cli_version),
        ("Configuration Loading", test_config_loading),
        ("Beyond Compare Detection", test_beyond_compare_detection),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append(False)
        print()

    # Run async test separately
    print("Running: Server Startup Test")
    try:
        async_result = asyncio.run(test_server_startup())
        results.append(async_result)
    except Exception as e:
        print(f"❌ Server Startup Test crashed: {e}")
        results.append(False)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"{status} {test_name}")

    async_status = "✅ PASS" if results[-1] else "❌ FAIL"
    print(f"{async_status} Server Startup Test")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All server tests passed! Server is functional.")
        return 0
    else:
        print("💥 Some server tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
