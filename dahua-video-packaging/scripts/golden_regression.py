#!/usr/bin/env python3
"""Create or verify deterministic visual identity reference frames."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS = SKILL_ROOT / "assets"
GOLDEN = ASSETS / "golden"
PROFILE = json.loads((ASSETS / "portable-profile.json").read_text(encoding="utf-8"))
BODY_FONT = ASSETS / PROFILE["fonts"]["body"]["file"]
CROSS_PLATFORM_MAX_CHANGED_RATIO = 0.05
CROSS_PLATFORM_MAX_MEAN_ERROR = 3.0
CROSS_PLATFORM_PIXEL_THRESHOLD = 12


def draw_fixture(mode: str) -> Image.Image:
    landscape = mode == "evidence-demo-landscape"
    size = (1920, 1080) if landscape else (1080, 1920)
    image = Image.new("RGB", size, PROFILE["colors"]["black"])
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(str(BODY_FONT), 72 if landscape else 64)
    body = ImageFont.truetype(str(BODY_FONT), 44 if landscape else 48)
    yellow = PROFILE["colors"]["yellow"]
    paper = PROFILE["colors"]["paper"]
    red = PROFILE["colors"]["red"]
    margin = 90 if landscape else 60
    draw.text((margin, 100), "AI 新媒体工作台", font=title, fill=paper)
    draw.rounded_rectangle((margin, 260, size[0] - margin, 570 if landscape else 760), radius=32, fill=(14, 14, 14), outline=paper, width=1)
    draw.text((margin + 36, 310), "输入素材", font=body, fill=paper)
    draw.line((margin + 250, 340, margin + 430, 340), fill=yellow, width=4)
    draw.polygon(((margin + 430, 330), (margin + 450, 340), (margin + 430, 350)), fill=yellow)
    draw.text((margin + 485, 310), "生成内容", font=body, fill=yellow)
    draw.text((margin + 36, 430), "固定字体 · 固定色系 · 固定动效", font=body, fill=paper)
    draw.line((margin + 36, 505, margin + 250, 505), fill=red, width=5)
    caption_y = 900 if landscape else 1180
    draw.rounded_rectangle((margin, caption_y, size[0] - margin, caption_y + 110), radius=34, fill=(0, 0, 0), outline=paper, width=1)
    caption = "同一套规则，换电脑也不漂移"
    bbox = draw.textbbox((0, 0), caption, font=body)
    draw.text(((size[0] - (bbox[2] - bbox[0])) / 2, caption_y + 22), caption, font=body, fill=paper)
    return image


def create() -> int:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for mode in ("fullframe", "small-window", "evidence-demo-landscape"):
        draw_fixture(mode).save(GOLDEN / f"{mode}.png", optimize=False)
    print(f"已生成黄金回归帧：{GOLDEN}")
    return 0


def difference_metrics(expected: Image.Image, actual: Image.Image) -> tuple[float, float]:
    difference = ImageChops.difference(expected, actual)
    channels = difference.split()
    strongest = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    significant = strongest.point(lambda value: 255 if value > CROSS_PLATFORM_PIXEL_THRESHOLD else 0)
    changed_pixels = significant.histogram()[255]
    changed_ratio = changed_pixels / (expected.width * expected.height)
    histogram = difference.histogram()
    channel_pixels = expected.width * expected.height * 3
    mean_error = sum((index % 256) * count for index, count in enumerate(histogram)) / channel_pixels
    return changed_ratio, mean_error


def verify(cross_platform: bool = False) -> int:
    errors: list[str] = []
    for mode in ("fullframe", "small-window", "evidence-demo-landscape"):
        path = GOLDEN / f"{mode}.png"
        if not path.is_file():
            errors.append(f"缺少 {path.name}")
            continue
        expected = Image.open(path).convert("RGB")
        actual = draw_fixture(mode)
        difference = ImageChops.difference(expected, actual)
        if difference.getbbox() is None:
            continue
        if not cross_platform:
            errors.append(f"{path.name} 像素不一致")
            continue
        changed_ratio, mean_error = difference_metrics(expected, actual)
        print(f"{path.name}: changed={changed_ratio:.4%}, mean_error={mean_error:.4f}")
        if changed_ratio > CROSS_PLATFORM_MAX_CHANGED_RATIO or mean_error > CROSS_PLATFORM_MAX_MEAN_ERROR:
            errors.append(
                f"{path.name} 超出跨平台容差：changed={changed_ratio:.4%}, mean_error={mean_error:.4f}"
            )
    if errors:
        print("黄金回归失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print("黄金回归通过：三种模式的固定视觉身份未漂移。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("create", "verify"))
    parser.add_argument(
        "--cross-platform",
        action="store_true",
        help="允许不同操作系统字体光栅化造成的小范围边缘差异；布局和大面积色彩漂移仍会失败。",
    )
    args = parser.parse_args()
    return create() if args.command == "create" else verify(cross_platform=args.cross_platform)


if __name__ == "__main__":
    raise SystemExit(main())
