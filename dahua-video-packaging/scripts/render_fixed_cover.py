from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SKILL_ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = SKILL_ROOT / "assets" / "fonts" / "SmileySans-Oblique.ttf"

WIDTH = 1920
HEIGHT = 1080
BACKGROUND = "#000000"
SAFE_CROP = (555, 0, 1365, 1080)
PREVIEW_SIZE = (1080, 1440)

LINE1_SIZE = 174
LINE1_TOP = 116
LINE1_COLORS = ((191, 217, 254), (35, 83, 148))
LINE2_SIZE = 82
LINE2_TOP = 290
LINE2_COLORS = ((191, 217, 254), (35, 83, 148), (32, 54, 93))
MAX_SAFE_TEXT_WIDTH = 760

PERSON_SIZE = (520, 924)
PERSON_POS = (700, 185)
PERSON_FEATHER = 56


def run_ffmpeg(source: Path, timestamp: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            str(output),
        ],
        check=True,
    )


def chinese_count(text: str) -> int:
    return sum("\u4e00" <= char <= "\u9fff" for char in text)


def text_metrics(text: str, font_size: int) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    font = ImageFont.truetype(str(FONT_PATH), font_size)
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
    return font, bbox


def validate_title(line1: str, line2: str) -> None:
    if chinese_count(line1) > 5:
        raise ValueError("第一行超过 5 个汉字；请改写标题，禁止缩小字号。")
    for label, text, size in (("第一行", line1, LINE1_SIZE), ("第二行", line2, LINE2_SIZE)):
        _, bbox = text_metrics(text, size)
        width = bbox[2] - bbox[0]
        if width > MAX_SAFE_TEXT_WIDTH:
            raise ValueError(
                f"{label}宽度 {width}px 超过固定安全宽度 {MAX_SAFE_TEXT_WIDTH}px；"
                "请改写标题，禁止缩小字号或改变坐标。"
            )


def gradient_text(
    canvas: Image.Image,
    text: str,
    font_size: int,
    top: int,
    colors: tuple[tuple[int, int, int], ...],
) -> None:
    font, bbox = text_metrics(text, font_size)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (WIDTH - text_width) // 2
    y = top - bbox[1]

    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(mask).text((x, y), text, font=font, fill=255)
    gradient = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(gradient)
    for yy in range(top, min(HEIGHT, top + text_height + 2)):
        u = 0 if text_height <= 1 else (yy - top) / text_height
        if len(colors) == 2:
            c0, c1 = colors
            local = u
        elif u <= 0.5:
            c0, c1 = colors[0], colors[1]
            local = u * 2
        else:
            c0, c1 = colors[1], colors[2]
            local = (u - 0.5) * 2
        color = tuple(round(c0[i] + (c1[i] - c0[i]) * local) for i in range(3))
        draw.line((x, yy, x + text_width + 2, yy), fill=color)
    canvas.paste(gradient, (0, 0), mask)


def place_person(canvas: Image.Image, source_frame: Image.Image) -> None:
    if source_frame.height <= source_frame.width:
        raise ValueError("封面人物源帧必须是竖屏真实口播帧。")
    person = source_frame.convert("RGB").resize(PERSON_SIZE, Image.Resampling.LANCZOS)
    alpha = Image.new("L", PERSON_SIZE, 255)
    pixels = alpha.load()
    for y in range(PERSON_SIZE[1]):
        top_alpha = min(255, round(255 * y / PERSON_FEATHER)) if y < PERSON_FEATHER else 255
        for x in range(PERSON_SIZE[0]):
            edge = min(x, PERSON_SIZE[0] - 1 - x)
            side_alpha = min(255, round(255 * edge / PERSON_FEATHER)) if edge < PERSON_FEATHER else 255
            pixels[x, y] = min(top_alpha, side_alpha)
    canvas.paste(person, PERSON_POS, alpha)


def render_cover(source_frame: Path, line1: str, line2: str) -> Image.Image:
    validate_title(line1, line2)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    place_person(canvas, Image.open(source_frame))
    gradient_text(canvas, line1, LINE1_SIZE, LINE1_TOP, LINE1_COLORS)
    gradient_text(canvas, line2, LINE2_SIZE, LINE2_TOP, LINE2_COLORS)
    return canvas


def save_master_and_preview(cover: Image.Image, master: Path, preview: Path) -> None:
    master.parent.mkdir(parents=True, exist_ok=True)
    preview.parent.mkdir(parents=True, exist_ok=True)
    cover.save(master)
    cover.crop(SAFE_CROP).resize(PREVIEW_SIZE, Image.Resampling.LANCZOS).save(preview)


def render_final(args: argparse.Namespace) -> None:
    frame = args.output_master.parent / "cover_selected_source.png"
    run_ffmpeg(args.source, args.timestamp, frame)
    cover = render_cover(frame, args.line1, args.line2)
    save_master_and_preview(cover, args.output_master, args.output_preview)


def render_candidates(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    previews: list[Image.Image] = []
    for index, timestamp in enumerate(args.timestamps, start=1):
        frame = args.output_dir / f"cover_source_{index}.png"
        master = args.output_dir / f"cover_candidate_{index}_master.png"
        preview = args.output_dir / f"cover_candidate_{index}_home_preview.png"
        run_ffmpeg(args.source, timestamp, frame)
        cover = render_cover(frame, args.line1, args.line2)
        save_master_and_preview(cover, master, preview)
        previews.append(Image.open(preview).convert("RGB"))

    sheet = Image.new("RGB", (1080, 480), BACKGROUND)
    for index, preview in enumerate(previews):
        sheet.paste(preview.resize((360, 480), Image.Resampling.LANCZOS), (index * 360, 0))
    sheet.save(args.output_dir / "cover_candidates_home_contact_sheet.png")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the frozen Dahua landscape cover template.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    final_parser = subparsers.add_parser("final")
    final_parser.add_argument("--source", type=Path, required=True)
    final_parser.add_argument("--timestamp", type=float, required=True)
    final_parser.add_argument("--line1", required=True)
    final_parser.add_argument("--line2", required=True)
    final_parser.add_argument("--output-master", type=Path, required=True)
    final_parser.add_argument("--output-preview", type=Path, required=True)
    final_parser.set_defaults(func=render_final)

    candidates_parser = subparsers.add_parser("candidates")
    candidates_parser.add_argument("--source", type=Path, required=True)
    candidates_parser.add_argument("--timestamps", type=float, nargs=3, required=True)
    candidates_parser.add_argument("--line1", required=True)
    candidates_parser.add_argument("--line2", required=True)
    candidates_parser.add_argument("--output-dir", type=Path, required=True)
    candidates_parser.set_defaults(func=render_candidates)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
