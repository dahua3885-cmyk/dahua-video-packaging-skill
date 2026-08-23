#!/usr/bin/env python3
"""Audit a release tree for private paths, identities, secrets, and missing licenses."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TEXT_EXTENSIONS = {".md", ".json", ".py", ".ps1", ".js", ".mjs", ".css", ".html", ".yaml", ".yml", ".txt"}
FORBIDDEN = {
    "private Windows user": re.compile(r"C:[/\\]Users[/\\](?!<|\{|\$)[^/\\\s]+", re.I),
    "private drive path": re.compile(r"\b[A-Z]:[/\\](?:视频剪辑|AI操作系统运行数据|Users)[/\\]", re.I),
    "noncommercial font": re.compile(r"新青年体|Non-Commercial Use", re.I),
    "credential": re.compile(r"(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*['\"][^'\"]{8,}", re.I),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    for path in root.rglob("*"):
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS or ".git" in path.parts or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for label, pattern in FORBIDDEN.items():
            if pattern.search(text):
                errors.append(f"{path.relative_to(root)}: {label}")
    required = (
        "SKILL.md",
        "assets/portable-profile.json",
        "assets/product-notice.json",
        "assets/fonts/OFL-NotoSansSC.txt",
        "assets/fonts/OFL-SmileySans.txt",
    )
    for name in required:
        if not (root / name).is_file():
            errors.append(f"缺少发布文件：{name}")
    if errors:
        print("开源审计失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("开源审计通过：未发现私有路径、身份、密钥或不可发布字体。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
