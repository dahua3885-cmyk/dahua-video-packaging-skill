#!/usr/bin/env python3
"""Install the bundled Skill atomically into the current user's Codex skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SOURCE = REPO_ROOT / "dahua-video-packaging"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"
    parser.add_argument("--skills-root", type=Path, default=default_root)
    args = parser.parse_args()
    root = args.skills_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not (SOURCE / "SKILL.md").is_file():
        raise SystemExit(f"Missing Skill source: {SOURCE}")
    subprocess.run(["python", str(SOURCE / "scripts" / "audit_open_source.py"), str(SOURCE)], check=True)
    stage = Path(tempfile.mkdtemp(prefix=".dahua-install-", dir=root))
    shutil.copytree(SOURCE, stage / SOURCE.name, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    staged = stage / SOURCE.name
    subprocess.run(["npm", "ci", "--prefix", str(staged / "assets" / "runtime"), "--ignore-scripts", "--no-audit", "--no-fund"], check=True)
    subprocess.run(["python", str(staged / "scripts" / "doctor.py")], check=True)
    target = root / SOURCE.name
    if target.exists():
        archive = root.parent / "skills-archive" / "dahua-video-packaging-installs"
        archive.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), archive / f"{SOURCE.name}-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.move(str(staged), target)
    stage.rmdir()
    print(f"Installed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
