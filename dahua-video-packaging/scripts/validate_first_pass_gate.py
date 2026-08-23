from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


FILENAME = "first_pass_gate.json"
WORKFLOWS = ("small-window", "evidence-demo", "talking-head", "skill-demo")
LAYOUT_MODES = ("vertical", "landscape")
TEMPLATES = {
    "cover",
    "topic-overview",
    "question-evidence",
    "gate-intro",
    "evidence-full",
    "interview-case",
    "process-build",
    "relationship-summary",
    "comparison",
    "conclusion",
}
ROLES = {"intro", "gate", "case", "explanation", "conclusion"}
EVIDENCE_TYPES = {
    "account-home",
    "works-grid",
    "original-video",
    "legacy-final-video",
    "process-recording",
    "real-screenshot",
    "real-image",
    "semantic-page",
    "none",
}
FILE_EVIDENCE_TYPES = EVIDENCE_TYPES - {"semantic-page", "none"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def absolute_file(value: str, field: str, problems: list[str]) -> Path | None:
    if not value:
        problems.append(f"{field}: missing path")
        return None
    path = Path(value)
    if not path.is_absolute():
        problems.append(f"{field}: path must be absolute: {value}")
    if not path.is_file():
        problems.append(f"{field}: file not found: {value}")
        return None
    return path


def source_record(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256(path.resolve())}


def init_gate(project_dir: Path, workflow: str, source_video: Path, baseline: Path | None, layout_mode: str) -> int:
    if not source_video.is_file():
        print(f"Source video not found: {source_video}", file=sys.stderr)
        return 1
    if baseline is not None and not baseline.is_file():
        print(f"Baseline version not found: {baseline}", file=sys.stderr)
        return 1
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir.resolve() / FILENAME
    if target.exists():
        print(f"Refusing to overwrite existing gate: {target}", file=sys.stderr)
        return 1
    data = {
        "schemaVersion": 1,
        "workflow": workflow,
        "project": {
            "sourceVideo": source_record(source_video),
            "baseline": {"mode": "revision", **source_record(baseline)} if baseline else {"mode": "new-build", "path": "", "sha256": ""},
            "changeScope": [],
            "frozenLayers": ["speaker", "captions", "approved-cover", "approved-modules"],
        },
        "cover": {
            "mode": "none",
            "source": "",
            "frozen": False,
            "lastCoverFrame": None,
            "firstBodyFrame": 0,
        },
        "output": {
            "stage": "sample",
            "layoutMode": layout_mode,
            "textDense": True,
            "width": 1440 if layout_mode == "vertical" else 1920,
            "height": 2560 if layout_mode == "vertical" else 1080,
            "fps": 30,
            "compositionEndFrame": 0,
            "speakerEndFrame": 0,
        },
        "scenes": [],
        "checkpoints": [],
        "approvals": {
            "baselineLocked": False,
            "semanticMapReviewed": False,
            "representativeGateReviewed": False,
        },
    }
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Initialized first-pass gate: {target}")
    print("Fill scenes, checkpoints and approvals; validation is expected to fail until evidence is complete.")
    return 0


def validate_gate(project_dir: Path, expected_workflow: str) -> int:
    target = project_dir.resolve() / FILENAME
    if not target.is_file():
        print(f"Missing first-pass gate: {target}", file=sys.stderr)
        return 1
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read {target}: {exc}", file=sys.stderr)
        return 1

    problems: list[str] = []
    if data.get("schemaVersion") != 1:
        problems.append("schemaVersion: expected 1")
    if data.get("workflow") != expected_workflow:
        problems.append(f"workflow: expected {expected_workflow!r}")

    project = data.get("project", {})
    source = project.get("sourceVideo", {})
    source_path = absolute_file(source.get("path", ""), "project.sourceVideo.path", problems)
    if source_path and source.get("sha256") != sha256(source_path):
        problems.append("project.sourceVideo.sha256: source changed after gate initialization")
    baseline = project.get("baseline", {})
    if baseline.get("mode") not in {"new-build", "revision"}:
        problems.append("project.baseline.mode: expected new-build or revision")
    if baseline.get("mode") == "revision":
        baseline_path = absolute_file(baseline.get("path", ""), "project.baseline.path", problems)
        if baseline_path and baseline.get("sha256") != sha256(baseline_path):
            problems.append("project.baseline.sha256: baseline changed after gate initialization")
    if not project.get("changeScope"):
        problems.append("project.changeScope: list the authorized build or revision scope")
    if not project.get("frozenLayers"):
        problems.append("project.frozenLayers: freeze confirmed layers")

    cover = data.get("cover", {})
    cover_mode = cover.get("mode")
    if cover_mode not in {"none", "source", "fixed"}:
        problems.append("cover.mode: expected none, source or fixed")
    if cover_mode in {"source", "fixed"}:
        absolute_file(cover.get("source", ""), "cover.source", problems)
        if not cover.get("frozen"):
            problems.append("cover.frozen: cover must be frozen before full render")
        last_cover = cover.get("lastCoverFrame")
        first_body = cover.get("firstBodyFrame")
        if not isinstance(last_cover, int) or not isinstance(first_body, int) or first_body != last_cover + 1:
            problems.append("cover boundary: firstBodyFrame must equal lastCoverFrame + 1")

    output = data.get("output", {})
    layout_mode = output.get("layoutMode")
    if layout_mode not in LAYOUT_MODES:
        problems.append("output.layoutMode: expected vertical or landscape")
    if output.get("stage") not in {"sample", "publish"}:
        problems.append("output.stage: expected sample or publish")
    if layout_mode == "vertical" and output.get("stage") == "publish" and output.get("textDense"):
        if (output.get("width"), output.get("height")) != (1440, 2560):
            problems.append("output: text-dense vertical publish must be native 1440x2560")
    composition_end = output.get("compositionEndFrame")
    speaker_end = output.get("speakerEndFrame")
    if not isinstance(composition_end, int) or composition_end <= 0:
        problems.append("output.compositionEndFrame: must be a positive integer")
    if not isinstance(speaker_end, int) or speaker_end < (composition_end if isinstance(composition_end, int) else 0):
        problems.append("output.speakerEndFrame: speaker must cover the composition last frame")

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        problems.append("scenes: add the complete semantic scene map")
        scenes = []
    ids: set[str] = set()
    used_templates: set[str] = set()
    previous = None
    for index, scene in enumerate(scenes):
        prefix = f"scenes[{index}]"
        scene_id = scene.get("id")
        if not scene_id or scene_id in ids:
            problems.append(f"{prefix}.id: missing or duplicate")
        ids.add(scene_id)
        template = scene.get("templateId")
        if template not in TEMPLATES:
            problems.append(f"{prefix}.templateId: unsupported template {template!r}")
        else:
            used_templates.add(template)
        if scene.get("sectionRole") not in ROLES:
            problems.append(f"{prefix}.sectionRole: unsupported role")
        start, end, trigger = scene.get("startFrame"), scene.get("endFrame"), scene.get("triggerFrame")
        if not all(isinstance(value, int) for value in (start, end, trigger)) or not (start <= trigger <= end):
            problems.append(f"{prefix}: require integer startFrame <= triggerFrame <= endFrame")
        if previous and isinstance(start, int) and isinstance(previous.get("endFrame"), int) and start <= previous["endFrame"]:
            problems.append(f"{prefix}.startFrame: scenes overlap or are unsorted")
        evidence_type = scene.get("evidenceType")
        if evidence_type not in EVIDENCE_TYPES:
            problems.append(f"{prefix}.evidenceType: unsupported type {evidence_type!r}")
        if evidence_type in FILE_EVIDENCE_TYPES:
            absolute_file(scene.get("visualSource", ""), f"{prefix}.visualSource", problems)
        if not scene.get("spokenCue"):
            problems.append(f"{prefix}.spokenCue: required")
        if not scene.get("persistKey"):
            problems.append(f"{prefix}.persistKey: required")
        states = scene.get("requiredStates", [])
        if not isinstance(states, list):
            problems.append(f"{prefix}.requiredStates: expected list")
            states = []
        last_state_frame = start if isinstance(start, int) else 0
        for state_index, state in enumerate(states):
            frame = state.get("frame")
            if not state.get("cue") or not isinstance(frame, int) or not isinstance(start, int) or not isinstance(end, int) or not (start <= frame <= end) or frame < last_state_frame:
                problems.append(f"{prefix}.requiredStates[{state_index}]: require cue and ascending in-scene frame")
            elif isinstance(frame, int):
                last_state_frame = frame
        check_frames = scene.get("checkFrames", [])
        if not isinstance(check_frames, list) or not all(isinstance(frame, int) for frame in check_frames):
            problems.append(f"{prefix}.checkFrames: expected integer list")
        elif all(isinstance(value, int) for value in (start, end, trigger)) and not {start, trigger, end}.issubset(set(check_frames)):
            problems.append(f"{prefix}.checkFrames: must include startFrame, triggerFrame and endFrame")
        if previous:
            same_visual = scene.get("visualSource") and scene.get("visualSource") == previous.get("visualSource")
            if same_visual and scene.get("persistKey") != previous.get("persistKey"):
                problems.append(f"{prefix}.persistKey: same adjacent evidence must reuse one container")
            if previous.get("sectionRole") == "gate" and scene.get("sectionRole") != "case":
                problems.append(f"{prefix}.sectionRole: every gate must be followed by its case")
        previous = scene

    if not any(scene.get("sectionRole") == "conclusion" for scene in scenes):
        problems.append("scenes: add one conclusion scene")

    checkpoints = data.get("checkpoints")
    if not isinstance(checkpoints, list):
        checkpoints = []
        problems.append("checkpoints: expected list")
    checkpoint_types: set[str] = set()
    template_checks: set[str] = set()
    for index, checkpoint in enumerate(checkpoints):
        prefix = f"checkpoints[{index}]"
        checkpoint_type = checkpoint.get("type")
        checkpoint_types.add(checkpoint_type)
        if checkpoint_type == "template-check":
            template_checks.add(checkpoint.get("templateId"))
        artifact = absolute_file(checkpoint.get("artifact", ""), f"{prefix}.artifact", problems)
        frames = checkpoint.get("frames", [])
        if artifact is None or not isinstance(frames, list) or not frames or not all(isinstance(frame, int) for frame in frames):
            problems.append(f"{prefix}: require existing artifact and integer frames")
    required_checkpoint_types = {"opening", "first-evidence-trigger", "conclusion", "last-frame"}
    if cover_mode != "none":
        required_checkpoint_types.add("cover-body-boundary")
    if any(scene.get("sectionRole") == "gate" for scene in scenes):
        required_checkpoint_types.add("gate-case-boundary")
    for missing in sorted(required_checkpoint_types - checkpoint_types):
        problems.append(f"checkpoints: missing {missing}")
    for missing in sorted(used_templates - template_checks):
        problems.append(f"checkpoints: template {missing!r} has no representative artifact")

    approvals = data.get("approvals", {})
    for key in ("baselineLocked", "semanticMapReviewed", "representativeGateReviewed"):
        if approvals.get(key) is not True:
            problems.append(f"approvals.{key}: must be true")

    if problems:
        print("First-pass quality gate failed:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"First-pass quality gate valid: {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize or validate Dahua video first-pass quality evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("project_dir", type=Path)
    init_parser.add_argument("--workflow", choices=WORKFLOWS, required=True)
    init_parser.add_argument("--source-video", type=Path, required=True)
    init_parser.add_argument("--baseline-version", type=Path)
    init_parser.add_argument("--layout-mode", choices=LAYOUT_MODES, required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("project_dir", type=Path)
    validate_parser.add_argument("--workflow", choices=WORKFLOWS, required=True)
    args = parser.parse_args()
    if args.command == "init":
        return init_gate(args.project_dir, args.workflow, args.source_video, args.baseline_version, args.layout_mode)
    return validate_gate(args.project_dir, args.workflow)


if __name__ == "__main__":
    raise SystemExit(main())
