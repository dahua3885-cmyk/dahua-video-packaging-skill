#!/usr/bin/env python3
"""Initialize and validate the unified Dahua packaging mode contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


FILENAME = "packaging_mode.json"
MODES = ("fullframe", "small-window", "evidence-demo")
LAYOUTS = ("vertical", "landscape")
SKILL_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = SKILL_ROOT / "assets" / "portable-profile.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def absolute_existing_file(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} 必须是绝对路径：{value}")
    if not path.is_file():
        raise ValueError(f"{label} 不存在：{value}")
    return path.resolve()


def init_contract(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    contract_path = project / FILENAME
    if contract_path.exists():
        raise ValueError(f"合同已存在，拒绝覆盖：{contract_path}")
    if args.mode != "evidence-demo" and args.layout_mode == "landscape":
        raise ValueError(f"{args.mode} 只允许 vertical；横屏比较使用 evidence-demo")

    source = absolute_existing_file(args.source_video, "sourceVideo")
    baseline = None
    if args.baseline_video:
        baseline = absolute_existing_file(args.baseline_video, "baselineVideo")

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "schemaVersion": 2,
        "profileId": profile["profileId"],
        "profileVersion": profile["profileVersion"],
        "profileSha256": sha256(PROFILE_PATH),
        "mode": args.mode,
        "layoutMode": args.layout_mode,
        "sourceVideo": str(source),
        "sourceSha256": sha256(source),
        "baselineVideo": str(baseline) if baseline else None,
        "baselineSha256": sha256(baseline) if baseline else None,
        "authorizedScope": [],
        "frozenLayers": ["audio", "cuts", "captions", "speaker", "cover", "cards", "assets", "color"],
        "locked": False,
    }
    contract_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已初始化：{contract_path}")
    print("请填写 authorizedScope、校准 frozenLayers，并把 locked 改为 true。")
    return 0


def validate_hash(data: dict[str, Any], path_key: str, hash_key: str, errors: list[str]) -> None:
    value = data.get(path_key)
    if not value:
        return
    try:
        path = absolute_existing_file(str(value), path_key)
    except ValueError as exc:
        errors.append(str(exc))
        return
    expected = data.get(hash_key)
    actual = sha256(path)
    if not expected:
        errors.append(f"{hash_key} 不能为空")
    elif expected != actual:
        errors.append(f"{path_key} 哈希已变化：{path}")


def validate_contract(args: argparse.Namespace) -> int:
    contract_path = Path(args.project).resolve() / FILENAME
    if not contract_path.is_file():
        raise ValueError(f"缺少合同：{contract_path}")
    data = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    errors: list[str] = []
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    if data.get("schemaVersion") != 2:
        errors.append("schemaVersion 必须为 2；旧工程请另存新版本并重新初始化")
    if data.get("profileId") != profile["profileId"]:
        errors.append("profileId 与当前固定配置不一致")
    if data.get("profileVersion") != profile["profileVersion"]:
        errors.append("profileVersion 与当前固定配置不一致")
    if data.get("profileSha256") != sha256(PROFILE_PATH):
        errors.append("profileSha256 与当前固定配置不一致")

    mode = data.get("mode")
    layout = data.get("layoutMode")
    if mode not in MODES:
        errors.append(f"mode 必须是：{', '.join(MODES)}")
    if args.mode and mode != args.mode:
        errors.append(f"模式不一致：合同={mode}，当前命令={args.mode}")
    if layout not in LAYOUTS:
        errors.append(f"layoutMode 必须是：{', '.join(LAYOUTS)}")
    if mode != "evidence-demo" and layout == "landscape":
        errors.append(f"{mode} 不允许 landscape")

    validate_hash(data, "sourceVideo", "sourceSha256", errors)
    if data.get("baselineVideo") or data.get("baselineSha256"):
        validate_hash(data, "baselineVideo", "baselineSha256", errors)
    if not isinstance(data.get("authorizedScope"), list) or not data.get("authorizedScope"):
        errors.append("authorizedScope 必须是非空列表")
    if not isinstance(data.get("frozenLayers"), list) or not data.get("frozenLayers"):
        errors.append("frozenLayers 必须是非空列表")
    if data.get("locked") is not True:
        errors.append("locked 必须为 true")

    if errors:
        print("模式合同未通过：")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"模式合同通过：{mode} / {layout}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化 packaging_mode.json")
    init_parser.add_argument("project")
    init_parser.add_argument("--mode", choices=MODES, required=True)
    init_parser.add_argument("--source-video", required=True)
    init_parser.add_argument("--baseline-video")
    init_parser.add_argument("--layout-mode", choices=LAYOUTS, default="vertical")
    init_parser.set_defaults(func=init_contract)

    validate_parser = subparsers.add_parser("validate", help="校验 packaging_mode.json")
    validate_parser.add_argument("project")
    validate_parser.add_argument("--mode", choices=MODES)
    validate_parser.set_defaults(func=validate_contract)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
