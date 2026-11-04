#!/usr/bin/env python3
"""Build a source release from an explicit list; never package runtime data."""
import argparse
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from formats import VERSION

ROOT_FILES = {"server.py", "formats.py", "start.py", "requirements.txt", "Start.command", "Aktualisieren.command", "Start.bat", "Aktualisieren.bat", "Start.sh", "README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md", ".gitignore", ".gitattributes", ".editorconfig"}
SOURCE_DIRS = {"web", "docs", "tests", "tools", ".github"}


def source_files(root=ROOT):
    for name in sorted(ROOT_FILES):
        file = root / name
        if not file.is_file():
            raise FileNotFoundError(f"Missing required project file: {name}")
        yield file
    for directory in sorted(SOURCE_DIRS):
        for file in sorted((root / directory).rglob("*")):
            if file.is_file() and not file.is_symlink() and not any(part.startswith("__pycache__") for part in file.parts) and file.suffix not in (".pyc", ".pyo") and file.name != ".DS_Store":
                yield file


def package(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    files = list(source_files())
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            relative = file.relative_to(ROOT)
            entry = zipfile.ZipInfo.from_file(file, "Frame/" + relative.as_posix())
            if file.suffix in (".command", ".sh"):
                entry.create_system = 3
                entry.external_attr = 0o100755 << 16
            archive.writestr(entry, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive verification failed")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "  " + output.name + "\n", encoding="utf-8")
    print(f"Created {output.name}: {len(files)} source files, {output.stat().st_size:,} bytes")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a clean Frame source ZIP")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"Frame-v{VERSION}.zip")
    package(parser.parse_args().output.resolve())
