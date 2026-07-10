import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bridge_helpers import resolve_executable_path, validate_executable


class ExecutablePathTests(unittest.TestCase):
    def test_resolves_macos_app_bundle_to_inner_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = Path(temp_dir) / "autoremesher.app"
            executable = app / "Contents" / "MacOS" / "autoremesher"
            executable.parent.mkdir(parents=True)
            executable.touch()
            executable.chmod(0o755)

            self.assertEqual(resolve_executable_path(app), executable)

    def test_rejects_macos_app_bundle_without_inner_executable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = Path(temp_dir) / "autoremesher.app"
            (app / "Contents" / "MacOS").mkdir(parents=True)

            with mock.patch("bridge_helpers.sys.platform", "darwin"):
                error = validate_executable(app)

            self.assertIn("executable not found", error)

    def test_accepts_direct_executable_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "autoremesher.exe"
            executable.touch()

            self.assertEqual(validate_executable(executable), "")

    def test_rejects_empty_path(self):
        self.assertIn("not configured", validate_executable(Path()))


if __name__ == "__main__":
    unittest.main()
