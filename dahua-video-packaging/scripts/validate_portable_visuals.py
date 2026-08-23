#!/usr/bin/env python3
"""Reject visual drift outside the frozen portable profile."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((SKILL_ROOT / "assets" / "portable-profile.json").read_text(encoding="utf-8"))
TEXT_EXTENSIONS = {".html", ".css", ".js", ".mjs", ".ts", ".tsx", ".json"}
SKIP_DIRS = {"node_modules", ".git", ".dahua-portable"}
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
RGB_RE = re.compile(r"rgba?\([^)]*\)", re.I)


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    allowed_colors = {value.upper() for value in PROFILE["colors"].values()}
    allowed_rgb = {re.sub(r"\s+", "", value).lower() for value in PROFILE["allowedCssRgbFunctions"]}
    forbidden = [term.lower() for term in PROFILE["motion"]["forbiddenTerms"]]
    allowed_eases = set(PROFILE["motion"]["allowedEases"])
    errors: list[str] = []
    root = args.project.resolve()
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        lowered = text.lower()
        rel = path.relative_to(root)
        for term in forbidden:
            if term in lowered:
                errors.append(f"{rel}: 禁止动效词 {term!r}")
        for color in sorted(set(HEX_RE.findall(text))):
            if color.upper() not in allowed_colors:
                errors.append(f"{rel}: 未授权颜色 {color}")
        for color in sorted(set(RGB_RE.findall(text))):
            normalized = re.sub(r"\s+", "", color).lower().replace(".0)", ")")
            normalized = re.sub(r",\.(\d+)", r",0.\1", normalized)
            if normalized not in allowed_rgb:
                errors.append(f"{rel}: 未授权 RGB/RGBA 颜色 {color}")
        for ease in re.findall(r"ease\s*:\s*['\"]([^'\"]+)['\"]", text):
            if ease not in allowed_eases:
                errors.append(f"{rel}: 未授权 easing {ease}")
    if errors:
        print("视觉漂移校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("视觉漂移校验通过：颜色、字体与动效未超出 dahua-portable-v1。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
