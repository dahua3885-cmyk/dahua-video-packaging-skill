#!/usr/bin/env python3
"""Check the local runtime required for reproducible packaging."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((SKILL_ROOT / "assets" / "portable-profile.json").read_text(encoding="utf-8"))


def output(command: list[str]) -> str:
    executable = shutil.which(command[0])
    if not executable:
        raise FileNotFoundError(command[0])
    resolved = [executable, *command[1:]]
    return subprocess.run(resolved, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    runtime = PROFILE["runtime"]
    checks = (("node", ["node", "--version"], runtime["node"]), ("npm", ["npm", "--version"], runtime["npm"]))
    for label, command, expected in checks:
        if not shutil.which(command[0]):
            errors.append(f"缺少 {label}")
            continue
        actual = output(command).lstrip("v")
        if actual != expected:
            errors.append(f"{label} 版本不一致：需要 {expected}，当前 {actual}")
    if sys.version.split()[0] != runtime["python"]:
        errors.append(f"Python 版本不一致：需要 {runtime['python']}，当前 {sys.version.split()[0]}")
    try:
        import PIL  # type: ignore
        if PIL.__version__ != runtime["pillow"]:
            errors.append(f"Pillow 版本不一致：需要 {runtime['pillow']}，当前 {PIL.__version__}")
    except ImportError:
        errors.append("缺少 Pillow")
    if not shutil.which("ffmpeg"):
        errors.append("缺少 ffmpeg")
    else:
        version_line = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, errors="replace").stdout.splitlines()[0]
        if runtime["ffmpeg"]["versionPrefix"] not in version_line:
            errors.append(f"ffmpeg 版本不一致：需要 {runtime['ffmpeg']['versionPrefix']}，当前 {version_line}")
        build = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace")
        if "ass" not in build.stdout:
            errors.append("ffmpeg 缺少 libass/ass 字幕滤镜")
    for spec in PROFILE["fonts"].values():
        path = SKILL_ROOT / "assets" / spec["file"]
        if not path.is_file():
            errors.append(f"缺少字体：{spec['file']}")
        elif sha256(path) != spec["sha256"]:
            errors.append(f"字体哈希不一致：{spec['file']}")
    runtime_cli = SKILL_ROOT / "assets" / "runtime" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    if not runtime_cli.is_file():
        warnings.append("固定 HyperFrames 尚未安装；运行 npm ci --prefix assets/runtime")
    if errors:
        print("环境检查失败：")
        for item in errors:
            print(f"- {item}")
    else:
        print("环境检查通过。")
    for item in warnings:
        print(f"警告：{item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
