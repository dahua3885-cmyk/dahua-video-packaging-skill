from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BASELINES = {
    "landscape": SKILL_ROOT / "assets" / "landscape-layout-contract.json",
    "vertical": SKILL_ROOT / "assets" / "vertical-layout-contract.json",
}
PROJECT_FILENAME = "layout_contract.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def diff(expected, actual, path: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path or '<root>'}: expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                problems.append(f"{child}: missing")
            else:
                problems.extend(diff(value, actual[key], child))
        for key in actual.keys() - expected.keys():
            child = f"{path}.{key}" if path else key
            problems.append(f"{child}: unexpected field")
        return problems
    if expected != actual:
        problems.append(f"{path}: expected {expected!r}, got {actual!r}")
    return problems


def contract_path(project_dir: Path) -> Path:
    return project_dir.resolve() / PROJECT_FILENAME


def validate_required_assets(contract: dict) -> list[str]:
    problems: list[str] = []
    for key_path in (("caption", "fontFile"), ("cover", "fontFile")):
        value = contract
        for key in key_path:
            value = value.get(key) if isinstance(value, dict) else None
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            problems.append(f"{'.'.join(key_path)}: invalid font path")
        else:
            asset_path = Path(value)
            if not asset_path.is_absolute():
                asset_path = SKILL_ROOT / "assets" / asset_path
            if not asset_path.is_file():
                problems.append(f"{'.'.join(key_path)}: file not found: {asset_path}")
    return problems


def init_contract(project_dir: Path, mode: str) -> int:
    baseline = load_json(BASELINES[mode])
    asset_problems = validate_required_assets(baseline)
    if asset_problems:
        print("Fixed layout skill assets are incomplete:", file=sys.stderr)
        for problem in asset_problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    project_dir.mkdir(parents=True, exist_ok=True)
    target = contract_path(project_dir)
    if target.exists():
        problems = diff(baseline, load_json(target))
        if problems:
            print(f"Refusing to overwrite changed contract: {target}", file=sys.stderr)
            for problem in problems:
                print(f"- {problem}", file=sys.stderr)
            return 1
        print(f"Contract already valid: {target}")
        return 0
    shutil.copyfile(BASELINES[mode], target)
    print(f"Initialized fixed layout contract: {target}")
    return 0


def validate_contract(project_dir: Path, mode: str) -> int:
    baseline = load_json(BASELINES[mode])
    asset_problems = validate_required_assets(baseline)
    if asset_problems:
        print("Fixed layout skill assets are incomplete:", file=sys.stderr)
        for problem in asset_problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    target = contract_path(project_dir)
    if not target.exists():
        print(f"Missing project contract: {target}", file=sys.stderr)
        return 1
    problems = diff(baseline, load_json(target))
    if problems:
        print("Fixed layout contract validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"Fixed layout contract valid: {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize or validate a fixed Dahua demo-video layout."
    )
    parser.add_argument("command", choices=("init", "validate"))
    parser.add_argument("project_dir", type=Path)
    parser.add_argument(
        "--mode",
        choices=tuple(BASELINES),
        default="landscape",
        help="Layout baseline. Defaults to landscape for backward compatibility.",
    )
    args = parser.parse_args()
    if args.command == "init":
        return init_contract(args.project_dir, args.mode)
    return validate_contract(args.project_dir, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
