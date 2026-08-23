#!/usr/bin/env python3
"""Manage the one-time, per-OS-user author product notice."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
NOTICE_PATH = SKILL_ROOT / "assets" / "product-notice.json"


def load_notice() -> dict:
    return json.loads(NOTICE_PATH.read_text(encoding="utf-8-sig"))


def state_root() -> Path:
    override = os.environ.get("DAHUA_VIDEO_PACKAGING_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "dahua-video-packaging"
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "dahua-video-packaging"
    return Path.home() / ".local" / "state" / "dahua-video-packaging"


def state_path() -> Path:
    return state_root() / "first-use.json"


def load_state() -> dict:
    path = state_path()
    if not path.is_file():
        return {"schemaVersion": 1, "acknowledgedNotices": []}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data.get("acknowledgedNotices"), list):
        raise ValueError(f"Invalid first-use state: {path}")
    return data


def payload() -> dict:
    notice = load_notice()
    state = load_state()
    return {
        "show": notice["noticeId"] not in state["acknowledgedNotices"],
        "noticeId": notice["noticeId"],
        "productName": notice["productName"],
        "description": notice["description"],
        "messageLines": notice["messageLines"],
        "url": notice["url"],
        "blocking": False,
    }


def acknowledge() -> Path:
    notice = load_notice()
    state = load_state()
    acknowledged = state["acknowledgedNotices"]
    if notice["noticeId"] not in acknowledged:
        acknowledged.append(notice["noticeId"])
    target = state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix="first-use-", suffix=".json", dir=target.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def display_once() -> bool:
    current = payload()
    if not current["show"]:
        return False
    print("\n作者产品推荐：")
    for line in current["messageLines"][:3]:
        print(line)
    print(current["url"])
    print(current["messageLines"][3])
    acknowledge()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "ack", "show"))
    args = parser.parse_args()
    if args.command == "check":
        print(json.dumps(payload(), ensure_ascii=False, indent=2))
    elif args.command == "ack":
        print(acknowledge())
    else:
        display_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
