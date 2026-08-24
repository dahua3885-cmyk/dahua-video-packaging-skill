#!/usr/bin/env python3
"""Install the bundled Skill atomically into the current user's Codex skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("npm was not found. Install the locked Node.js/npm runtime and retry.")
    subprocess.run([sys.executable, str(SOURCE / "scripts" / "audit_open_source.py"), str(SOURCE)], check=True)
    stage = Path(tempfile.mkdtemp(prefix=".dahua-install-", dir=root))
    shutil.copytree(SOURCE, stage / SOURCE.name, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    staged = stage / SOURCE.name
    subprocess.run([npm, "ci", "--prefix", str(staged / "assets" / "runtime"), "--ignore-scripts", "--no-audit", "--no-fund"], check=True)
    subprocess.run([sys.executable, str(staged / "scripts" / "doctor.py")], check=True)
    target = root / SOURCE.name
    if target.exists():
        archive = root.parent / "skills-archive" / "dahua-video-packaging-installs"
        archive.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), archive / f"{SOURCE.name}-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.move(str(staged), target)
    stage.rmdir()
    print(f"Installed: {target}")
    try:
        notice = subprocess.run(
            [sys.executable, str(target / "scripts" / "first_use_notice.py"), "show"],
            check=False,
        )
        if notice.returncode != 0:
            print("首次作者产品推荐未能显示，不影响 Skill 安装和使用。", file=sys.stderr)
    except OSError as exc:
        print(f"首次作者产品推荐未能显示，不影响 Skill 安装和使用：{exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
