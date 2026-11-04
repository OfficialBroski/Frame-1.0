"""Ensure releases retain launcher permissions and exclude local files."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package import ROOT, ROOT_FILES, SOURCE_DIRS, package, source_files


class PackageTests(unittest.TestCase):
    def test_local_media_and_configuration_never_enter_source_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ROOT_FILES:
                (root / name).write_text("source", encoding="utf-8")
            for folder in ("downloads", ".runtime", ".git", ".venv", "web", "web/__pycache__"):
                (root / folder).mkdir(parents=True, exist_ok=True)
            for file in ("downloads/private.mp3", ".runtime/token", ".git/config", "frame.local.json", ".env", "web/__pycache__/private.pyc"):
                (root / file).write_text("private", encoding="utf-8")
            (root / "web/index.html").write_text("public", encoding="utf-8")
            paths = {path.relative_to(root).as_posix() for path in source_files(root)}
            self.assertEqual(paths, ROOT_FILES | {"web/index.html"})

    def test_source_zip_integrity_and_launch_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = package(Path(temporary) / "Frame.zip")
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn("Frame/README.md", archive.namelist())
                self.assertIn("Frame/.github/workflows/ci.yml", archive.namelist())
                self.assertTrue((archive.getinfo("Frame/Start.command").external_attr >> 16) & 0o111)
                self.assertFalse(any("/downloads/" in p or "/.runtime/" in p for p in archive.namelist()))
            self.assertTrue(output.with_suffix(".zip.sha256").is_file())
