#!/usr/bin/env python3
"""Initialize and validate a user-neutral, reproducible packaging project."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path



SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = SKILL_ROOT / "assets"
PROFILE_PATH = ASSETS_ROOT / "portable-profile.json"
LOCK_NAME = "portable_project.json"
SNAPSHOT_DIR = ".dahua-portable"
COPY_ASSETS = (
    "portable-profile.json",
    "fullframe-contract.css",
    "fullframe-motion-tokens.js",
    "landscape-layout-contract.json",
    "vertical-layout-contract.json",
    "fonts/NotoSansSC-VF.ttf",
    "fonts/SmileySans-Oblique.ttf",
    "fonts/OFL-NotoSansSC.txt",
    "fonts/OFL-SmileySans.txt",
    "runtime/package.json",
    "runtime/package-lock.json",
    "runtime/requirements-lock.txt",
    "golden/fullframe.png",
    "golden/small-window.png",
    "golden/evidence-demo-landscape.png",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def profile() -> dict:
    return load_json(PROFILE_PATH)


def canonical_manifest() -> dict[str, str]:
    missing = [name for name in COPY_ASSETS if not (ASSETS_ROOT / name).is_file()]
    if missing:
        raise ValueError("Skill 资产缺失：" + ", ".join(missing))
    return {name: sha256(ASSETS_ROOT / name) for name in COPY_ASSETS}


def init_project(project: Path, mode: str, layout: str) -> int:
    project = project.resolve()
    project.mkdir(parents=True, exist_ok=True)
    lock_path = project / LOCK_NAME
    if lock_path.exists():
        raise ValueError(f"锁文件已存在，拒绝覆盖：{lock_path}")
    if mode != "evidence-demo" and layout == "landscape":
        raise ValueError(f"{mode} 只允许 vertical")

    manifest = canonical_manifest()
    snapshot = project / SNAPSHOT_DIR
    for name in COPY_ASSETS:
        source = ASSETS_ROOT / name
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    current = profile()
    payload = {
        "schemaVersion": 1,
        "projectId": project.name,
        "profileId": current["profileId"],
        "profileVersion": current["profileVersion"],
        "profileSha256": sha256(PROFILE_PATH),
        "mode": mode,
        "layoutMode": layout,
        "strict": True,
        "assetManifest": manifest,
        "userIdentity": None,
    }
    lock_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已初始化可复现项目：{lock_path}")
    return 0


def validate_project(project: Path) -> int:
    project = project.resolve()
    lock_path = project / LOCK_NAME
    if not lock_path.is_file():
        raise ValueError(f"缺少锁文件：{lock_path}")
    data = load_json(lock_path)
    current = profile()
    expected = canonical_manifest()
    errors: list[str] = []
    if data.get("profileId") != current["profileId"]:
        errors.append("profileId 与当前 Skill 不一致")
    if data.get("profileVersion") != current["profileVersion"]:
        errors.append("profileVersion 与当前 Skill 不一致；请新建工程版本，不要静默升级")
    if data.get("profileSha256") != sha256(PROFILE_PATH):
        errors.append("profileSha256 与当前 Skill 不一致")
    if data.get("strict") is not True:
        errors.append("strict 必须为 true")
    if data.get("userIdentity") is not None:
        errors.append("公开项目锁不得写入用户身份")
    if data.get("assetManifest") != expected:
        errors.append("assetManifest 与当前 Skill 不一致")
    snapshot = project / SNAPSHOT_DIR
    for name, digest in expected.items():
        target = snapshot / name
        if not target.is_file():
            errors.append(f"项目快照缺失：{name}")
        elif sha256(target) != digest:
            errors.append(f"项目快照被修改：{name}")
    if errors:
        print("可复现项目校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"可复现项目校验通过：{data['profileId']}@{data['profileVersion']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("project", type=Path)
    init.add_argument("--mode", choices=("fullframe", "small-window", "evidence-demo"), required=True)
    init.add_argument("--layout", choices=("vertical", "landscape"), default="vertical")
    validate = sub.add_parser("validate")
    validate.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        return init_project(args.project, args.mode, args.layout) if args.command == "init" else validate_project(args.project)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
