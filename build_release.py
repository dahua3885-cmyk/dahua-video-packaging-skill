#!/usr/bin/env python3
"""Build a clean release ZIP plus SHA-256 checksum."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST = ROOT / "dist"
EXCLUDED_PARTS = {".git", "dist", "node_modules", "__pycache__"}


def include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    return not any(part in EXCLUDED_PARTS for part in rel.parts) and path.suffix != ".pyc"


def write_checksum(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (path.with_suffix(path.suffix + ".sha256")).write_text(f"{digest}  {path.name}\n", encoding="ascii")
    return digest


def main() -> int:
    skill = ROOT / "dahua-video-packaging"
    subprocess.run(["python", str(skill / "scripts" / "audit_open_source.py"), str(skill)], check=True)
    DIST.mkdir(exist_ok=True)
    repo_zip = DIST / f"dahua-video-packaging-skill-{VERSION}.zip"
    skill_zip = DIST / f"dahua-video-packaging-{VERSION}.zip"
    with tempfile.TemporaryDirectory(prefix="dahua-release-") as temp:
        staging = Path(temp) / f"dahua-video-packaging-skill-{VERSION}"
        for path in ROOT.rglob("*"):
            if not path.is_file() or not include(path):
                continue
            target = staging / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        with zipfile.ZipFile(repo_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging.parent))
        with zipfile.ZipFile(skill_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted((staging / "dahua-video-packaging").rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging))
    repo_digest = write_checksum(repo_zip)
    skill_digest = write_checksum(skill_zip)
    print(f"Built repository bundle: {repo_zip}")
    print(f"SHA256: {repo_digest}")
    print(f"Built Skill-only bundle: {skill_zip}")
    print(f"SHA256: {skill_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
