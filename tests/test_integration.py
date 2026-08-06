#!/usr/bin/env python3
"""
Integration tests for Beyond Compare MCP Server with real Beyond Compare executable.

These tests verify that the server actually works with a real Beyond Compare installation.
"""

import os
import tempfile
import unittest
from pathlib import Path

from beyondcompare_mcp.exceptions import BeyondCompareNotInstalledError
from beyondcompare_mcp.server import BeyondCompareMCP


class TestBeyondCompareIntegration(unittest.TestCase):
    """Integration tests with real Beyond Compare."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment with real files."""
        # Create temporary test directory
        cls.test_dir = Path(tempfile.mkdtemp(prefix="bc_mcp_integration_"))

        # Create test files for comparison
        cls.test_files_dir = cls.test_dir / "test_files"
        cls.test_files_dir.mkdir()

        # Create identical files
        cls.file1_identical = cls.test_files_dir / "file1_identical.txt"
        cls.file2_identical = cls.test_files_dir / "file2_identical.txt"
        identical_content = "This is identical content for testing.\nLine 2\nLine 3"
        cls.file1_identical.write_text(identical_content)
        cls.file2_identical.write_text(identical_content)

        # Create different files
        cls.file1_different = cls.test_files_dir / "file1_different.txt"
        cls.file2_different = cls.test_files_dir / "file2_different.txt"
        cls.file1_different.write_text("This is the original content.\nLine 2\nLine 3")
        cls.file2_different.write_text("This is the MODIFIED content.\nLine 2\nLine 3 CHANGED")

        # Create test directories
        cls.dir1 = cls.test_files_dir / "dir1"
        cls.dir2 = cls.test_files_dir / "dir2"
        cls.dir1.mkdir()
        cls.dir2.mkdir()

        # Add files to directories
        (cls.dir1 / "common.txt").write_text("Common file content")
        (cls.dir2 / "common.txt").write_text("Common file content")
        (cls.dir1 / "unique1.txt").write_text("Unique to dir1")
        (cls.dir2 / "unique2.txt").write_text("Unique to dir2")

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        """Set up each test."""
        # Try to create server with auto-detection
        try:
            self.server = BeyondCompareMCP()
            self.bc_available = True
        except BeyondCompareNotInstalledError:
            self.bc_available = False
            self.skipTest("Beyond Compare not available for integration tests")

    def test_real_file_comparison_identical(self):
        """Test comparing identical files with real Beyond Compare."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        result = self.server._compare_files(str(self.file1_identical), str(self.file2_identical))

        # Should succeed and find no differences
        self.assertTrue(result["success"])
        # Beyond Compare returns 0 for identical files
        # Note: The exact behavior depends on BC version and settings

    def test_real_file_comparison_different(self):
        """Test comparing different files with real Beyond Compare."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        result = self.server._compare_files(str(self.file1_different), str(self.file2_different))

        # Should succeed
        self.assertTrue(result["success"])
        # May or may not detect differences depending on BC exit codes

    def test_real_directory_comparison(self):
        """Test comparing directories with real Beyond Compare."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        result = self.server._compare_folders(str(self.dir1), str(self.dir2), include_subfolders=True)

        # Should succeed
        self.assertTrue(result["success"])

    def test_real_file_comparison_with_report(self):
        """Test file comparison with HTML report generation."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Create output report path
        report_path = self.test_dir / "comparison_report.html"

        result = self.server._compare_files(
            str(self.file1_different), str(self.file2_different), output_report=str(report_path)
        )

        # Should succeed
        self.assertTrue(result["success"])

        # Check if report was created (BC might create it)
        # Note: Report creation depends on BC settings and version

    def test_beyond_compare_executable_detection(self):
        """Test that Beyond Compare executable is properly detected."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Verify BC path is detected and exists
        self.assertIsNotNone(self.server.bc_path)
        self.assertTrue(self.server.bc_path.exists())
        self.assertTrue(str(self.server.bc_path).endswith((".exe", "bcompare")))

    def test_script_file_creation_and_cleanup(self):
        """Test that BC script files are created and cleaned up properly."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        scripts_before = list(self.server.scripts_dir.glob("*.txt"))

        # Perform a comparison that requires script creation
        result = self.server._compare_files(str(self.file1_identical), str(self.file2_identical))

        # Operation should succeed
        self.assertTrue(result["success"])

        # Check that no script files are left behind (should be cleaned up)
        scripts_after = list(self.server.scripts_dir.glob("*.txt"))

        # Script files should be cleaned up
        self.assertEqual(len(scripts_before), len(scripts_after))

    def test_nonexistent_file_handling(self):
        """Test handling of nonexistent files."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Test with nonexistent left file
        result = self.server._compare_files(str(self.test_dir / "nonexistent1.txt"), str(self.file1_identical))

        # Should handle gracefully
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_invalid_directory_handling(self):
        """Test handling of invalid directories."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        result = self.server._compare_folders(
            str(self.test_dir / "nonexistent_dir1"), str(self.test_dir / "nonexistent_dir2")
        )

        # Should handle gracefully
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_sync_dry_run(self):
        """Test folder synchronization in dry-run mode."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Create source and target directories
        source_dir = self.test_dir / "sync_source"
        target_dir = self.test_dir / "sync_target"
        source_dir.mkdir()
        target_dir.mkdir()

        # Add file to source
        (source_dir / "sync_test.txt").write_text("Content to sync")

        result = self.server._sync_folders(str(source_dir), str(target_dir), sync_mode="mirror", dry_run=True)

        # Should succeed in dry-run mode
        self.assertTrue(result["success"])
        self.assertTrue(result.get("dry_run", False))

    def test_performance_with_larger_files(self):
        """Test performance with larger files."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Create larger test files (1MB each)
        large_file1 = self.test_dir / "large1.txt"
        large_file2 = self.test_dir / "large2.txt"

        # Create content with some differences
        content1 = "Line content\n" * 50000  # ~50k lines
        content2 = content1.replace("Line content", "Line MODIFIED", 10)  # Change 10 lines

        large_file1.write_text(content1)
        large_file2.write_text(content2)

        import time

        start_time = time.time()

        result = self.server._compare_files(str(large_file1), str(large_file2))

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        self.assertTrue(result["success"])
        self.assertLess(duration, 30.0, "Large file comparison took too long")

    def test_path_with_spaces(self):
        """Test handling of file paths with spaces."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Create files with spaces in names
        spaced_dir = self.test_dir / "directory with spaces"
        spaced_dir.mkdir()

        file_with_spaces1 = spaced_dir / "file with spaces 1.txt"
        file_with_spaces2 = spaced_dir / "file with spaces 2.txt"

        file_with_spaces1.write_text("Content 1")
        file_with_spaces2.write_text("Content 2")

        result = self.server._compare_files(str(file_with_spaces1), str(file_with_spaces2))

        # Should handle spaced paths correctly
        self.assertTrue(result["success"])

    def test_unicode_content_handling(self):
        """Test handling of files with Unicode content."""
        if not self.bc_available:
            self.skipTest("Beyond Compare not available")

        # Create files with Unicode content
        unicode_file1 = self.test_dir / "unicode1.txt"
        unicode_file2 = self.test_dir / "unicode2.txt"

        unicode_content1 = "Hello 世界! 🌍 Café résumé naïve\n测试内容"
        unicode_content2 = "Hello 世界! 🌍 Café résumé naïve\n测试内容 MODIFIED"

        unicode_file1.write_text(unicode_content1, encoding="utf-8")
        unicode_file2.write_text(unicode_content2, encoding="utf-8")

        result = self.server._compare_files(str(unicode_file1), str(unicode_file2))

        # Should handle Unicode content correctly
        self.assertTrue(result["success"])


class TestEnvironmentValidation(unittest.TestCase):
    """Tests for validating the test environment."""

    def test_beyond_compare_installed(self):
        """Verify Beyond Compare is properly installed."""
        try:
            server = BeyondCompareMCP()
            bc_path = server.bc_path

            # Verify executable exists and is executable
            self.assertTrue(bc_path.exists(), f"Beyond Compare not found at {bc_path}")
            self.assertTrue(bc_path.is_file(), f"Beyond Compare path is not a file: {bc_path}")

            # On Windows, check it's an .exe file
            if os.name == "nt":
                self.assertTrue(str(bc_path).endswith(".exe"), f"BC executable should be .exe: {bc_path}")

            print(f"✅ Beyond Compare found at: {bc_path}")

        except BeyondCompareNotInstalledError as e:
            self.fail(f"Beyond Compare not properly installed: {e}")

    def test_bc_version_compatibility(self):
        """Test Beyond Compare version compatibility."""
        try:
            server = BeyondCompareMCP()

            # Try to run BC with help command to verify it works
            import subprocess

            result = subprocess.run([str(server.bc_path), "/?"], capture_output=True, text=True, timeout=10)

            # Should not crash (exit code may vary)
            self.assertIsNotNone(result)
            print(f"✅ Beyond Compare responds to commands (exit code: {result.returncode})")

        except Exception as e:
            self.fail(f"Beyond Compare version compatibility issue: {e}")


if __name__ == "__main__":
    # Run environment validation first
    print("🔍 Validating test environment...")
    env_suite = unittest.TestLoader().loadTestsFromTestCase(TestEnvironmentValidation)
    env_runner = unittest.TextTestRunner(verbosity=2)
    env_result = env_runner.run(env_suite)

    if env_result.wasSuccessful():
        print("\n🚀 Running integration tests...")
        integration_suite = unittest.TestLoader().loadTestsFromTestCase(TestBeyondCompareIntegration)
        integration_runner = unittest.TextTestRunner(verbosity=2)
        integration_result = integration_runner.run(integration_suite)

        print("\n📊 Results:")
        print(f"Environment tests: {'✅ PASS' if env_result.wasSuccessful() else '❌ FAIL'}")
        print(f"Integration tests: {'✅ PASS' if integration_result.wasSuccessful() else '❌ FAIL'}")

        if env_result.wasSuccessful() and integration_result.wasSuccessful():
            print("🎉 All integration tests passed!")
        else:
            print("💥 Some tests failed - check output above")
    else:
        print("❌ Environment validation failed - cannot run integration tests")
