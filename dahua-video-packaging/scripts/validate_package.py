#!/usr/bin/env python3
"""Validate Dahua full-frame caption and card production contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ALLOWED_PLACEMENTS = {"plain", "with-card"}
ALLOWED_PURPOSES = {"relation", "contrast", "process", "evidence", "conclusion"}
BASE_COMPONENTS = {"single-title", "title-detail", "compare-2", "flow-3", "audit-2", "conclusion", "media"}
STAGED_COMPONENTS = {"title-detail", "audit-2", "conclusion"}
ALLOWED_EDIT_REASONS = {"isolated-filler", "adjacent-repeat", "asr-correction", "numeric-style", "user-approved-removal"}
PROTECTED_TERMS = ("而且", "以及", "所以", "还有", "就是", "自己", "里面", "他就")
ATOMIC_BOUNDARY_TERMS = (
    "往往",
    "常常",
    "渐渐",
    "慢慢",
    "偏偏",
    "恰恰",
    "仅仅",
    "刚刚",
    "纷纷",
)
TRAILING_PRONOUNS = ("他们", "她们", "它们", "这个", "那个", "这些", "那些", "他", "她", "它")
PRONOUN_COMPOUND_EXCEPTIONS = ("其他", "吉他", "利他")
DEPENDENT_PREDICATE_PREFIXES = (
    "不一定",
    "一定要",
    "不是",
    "不应该",
    "不能",
    "不会",
    "不可以",
    "不需要",
    "没有",
    "没法",
    "要",
    "应该",
    "需要",
    "能够",
    "能",
    "会",
    "可以",
    "必须",
    "有",
    "把",
    "被",
)
ISOLATED_FILLERS = {"呃", "嗯", "啊", "呀", "嘛"}
FORBIDDEN_PUNCTUATION = re.compile(r"[，,。.!！；;：:“”‘’、…（）()【】\[\]《》<>]")
NONSTANDARD_ZERO_TO_ONE = re.compile(r"(?:零|0)\s*(?:到|至|～)\s*(?:一|1)")
SEMANTIC_MODES = {"explain"}
CAPTION_MAX_EQUIVALENT_EM = 15.0
ALLOWED_MOTION_MODES = {"static", "semantic-motion", "b-roll"}
BASELINE_ONLY_PATTERNS = {"fade", "slide", "card-enter", "node-enter", "title-reflow", "arrow-draw"}
GENERIC_GAIN_PHRASES = ("强调重点", "丰富画面", "增强节奏", "提升质感", "增加动感", "视觉更丰富")
COMPONENT_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MOTION_PATTERN_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def caption_equivalent_em(text: str) -> float:
    """Conservative width preflight; final acceptance still uses rendered pixels."""
    width = 0.0
    for char in text:
        if char.isspace():
            width += 0.35
        elif ord(char) < 128:
            width += 0.55
        else:
            width += 1.0
    return width


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def captions_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("captions"), list):
        return payload["captions"]
    raise ValueError("captions.json must be a list or an object containing a captions list")


def cards_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("cards"), list):
        return payload["cards"]
    raise ValueError("production-timeline.json must contain a cards list")


def as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def overlaps(start: float, end: float, card_start: float, card_end: float) -> bool:
    return start < card_end - 1e-6 and end > card_start + 1e-6


def normalized_text(value: str) -> str:
    return re.sub(r"[\s，,。.!！；;：:?？“”‘’、…（）()【】\[\]《》<>]", "", value)


def validate_caption_boundary(
    previous_id: str,
    previous_text: str,
    current_id: str,
    current_text: str,
    errors: list[str],
) -> None:
    """Catch deterministic cross-cue breaks; human semantic review remains mandatory."""
    previous = normalized_text(previous_text)
    current = normalized_text(current_text)
    if not previous or not current:
        return

    for term in ATOMIC_BOUNDARY_TERMS:
        for split_at in range(1, len(term)):
            if previous.endswith(term[:split_at]) and current.startswith(term[split_at:]):
                errors.append(
                    f"{previous_id} -> {current_id}: atomic term '{term}' is split across captions; "
                    "keep the complete word in one caption"
                )
                return

    if any(previous.endswith(exception) for exception in PRONOUN_COMPOUND_EXCEPTIONS):
        return
    pronoun = next((item for item in TRAILING_PRONOUNS if previous.endswith(item)), None)
    predicate = next((item for item in DEPENDENT_PREDICATE_PREFIXES if current.startswith(item)), None)
    if pronoun and predicate:
        errors.append(
            f"{previous_id} -> {current_id}: trailing pronoun '{pronoun}' is separated from "
            f"dependent predicate '{predicate}'; move the pronoun into the next caption"
        )


def validate_display_edits(cid: str, source: str, text: str, edits: Any, errors: list[str]) -> None:
    source_normalized = normalized_text(source)
    text_normalized = normalized_text(text)
    changed = source_normalized != text_normalized
    if not changed:
        if edits not in (None, []):
            errors.append(f"{cid}: displayEdits must be empty when sourceText and text differ only by punctuation/spacing")
        return
    if not isinstance(edits, list) or not edits:
        errors.append(f"{cid}: untracked display change; add displayEdits for every non-punctuation edit")
        return
    for edit_index, edit in enumerate(edits, 1):
        if not isinstance(edit, dict):
            errors.append(f"{cid}: displayEdits item {edit_index} must be an object")
            continue
        reason = edit.get("reason")
        if reason not in ALLOWED_EDIT_REASONS:
            errors.append(f"{cid}: displayEdits item {edit_index} has invalid reason '{reason}'")
        source_fragment = edit.get("from")
        replacement = edit.get("to")
        if not isinstance(source_fragment, str) or not source_fragment:
            errors.append(f"{cid}: displayEdits item {edit_index} requires a non-empty from value")
        elif normalized_text(source_fragment) not in source_normalized:
            errors.append(f"{cid}: displayEdits item {edit_index} from value is not present in sourceText")
        if not isinstance(replacement, str):
            errors.append(f"{cid}: displayEdits item {edit_index} requires a string to value")


def validate(
    captions: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    strict: bool,
    motion_policy: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    caption_ids: set[str] = set()
    card_ids: set[str] = set()
    caption_ranges: list[tuple[str, float, float]] = []
    caption_entries: list[tuple[str, float, float, str]] = []

    card_ranges: list[tuple[str, float, float, str]] = []
    qualifying_motion_cards = 0
    for index, card in enumerate(cards, 1):
        cid = str(card.get("id") or f"card-{index}")
        if cid in card_ids:
            errors.append(f"{cid}: duplicate card id")
        card_ids.add(cid)
        start = as_number(card.get("start"))
        end = as_number(card.get("end"))
        if start is None or end is None or end <= start:
            errors.append(f"{cid}: invalid card start/end")
            continue
        visual_slot = card.get("visualSlot", "card-band")
        if not isinstance(visual_slot, str) or not visual_slot.strip():
            errors.append(f"{cid}: visualSlot must be a non-empty string")
            visual_slot = "card-band"
        card_ranges.append((cid, start, end, visual_slot.strip()))

        purpose = card.get("purpose")
        if purpose not in ALLOWED_PURPOSES:
            message = f"{cid}: purpose must be one of {sorted(ALLOWED_PURPOSES)}"
            (errors if strict else warnings).append(message)

        understanding_gain = card.get("understandingGain")
        why_now = card.get("whyNow")
        if not isinstance(understanding_gain, str) or not understanding_gain.strip():
            errors.append(f"{cid}: understandingGain is required; state what understanding is lost if the package is removed")
        elif any(phrase in understanding_gain for phrase in GENERIC_GAIN_PHRASES):
            errors.append(f"{cid}: understandingGain must describe semantic value, not presentation value")
        if not isinstance(why_now, str) or not why_now.strip():
            errors.append(f"{cid}: whyNow is required; explain why the package starts at this cue and not earlier")

        component = card.get("component")
        if not isinstance(component, str) or not COMPONENT_NAME.fullmatch(component):
            errors.append(f"{cid}: component must be a non-empty kebab-case name")
        elif component not in BASE_COMPONENTS:
            visual_model = card.get("visualModel")
            why_this_visual = card.get("whyThisVisual")
            if not isinstance(visual_model, str) or not visual_model.strip():
                errors.append(f"{cid}: custom component '{component}' requires a non-empty visualModel")
            if not isinstance(why_this_visual, str) or not why_this_visual.strip():
                errors.append(f"{cid}: custom component '{component}' requires a non-empty whyThisVisual")

        motion_plan = card.get("motionPlan")
        if not isinstance(motion_plan, dict):
            errors.append(f"{cid}: motionPlan is required; audit static, semantic-motion, or b-roll explicitly")
        else:
            motion_mode = motion_plan.get("mode")
            semantic_intent = motion_plan.get("semanticIntent")
            if motion_mode not in ALLOWED_MOTION_MODES:
                errors.append(f"{cid}: motionPlan.mode must be one of {sorted(ALLOWED_MOTION_MODES)}")
            if not isinstance(semantic_intent, str) or not semantic_intent.strip():
                errors.append(f"{cid}: motionPlan.semanticIntent must explain what the viewer should understand")
            if motion_mode == "static":
                reason = motion_plan.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    errors.append(f"{cid}: static motionPlan requires a concrete reason")
            elif motion_mode in {"semantic-motion", "b-roll"}:
                pattern = motion_plan.get("pattern")
                actors = motion_plan.get("actors")
                if not isinstance(pattern, str) or not pattern.strip():
                    errors.append(f"{cid}: {motion_mode} motionPlan requires a non-empty pattern")
                elif not MOTION_PATTERN_NAME.fullmatch(pattern.strip()):
                    errors.append(f"{cid}: motionPlan.pattern must be a descriptive kebab-case name")
                elif motion_mode == "semantic-motion" and pattern.strip() in BASELINE_ONLY_PATTERNS:
                    errors.append(f"{cid}: pattern '{pattern}' is only a baseline transition, not semantic motion")
                if not isinstance(actors, list) or not actors or not all(isinstance(actor, str) and actor.strip() for actor in actors):
                    errors.append(f"{cid}: {motion_mode} motionPlan requires non-empty actors")
                if motion_mode == "semantic-motion":
                    motion_gain = motion_plan.get("motionGain")
                    if not isinstance(motion_gain, str) or not motion_gain.strip():
                        errors.append(f"{cid}: semantic-motion requires motionGain; state what understanding is lost without motion")
                    elif any(phrase in motion_gain for phrase in GENERIC_GAIN_PHRASES):
                        errors.append(f"{cid}: motionGain must describe semantic value, not presentation value")
                if (
                    isinstance(pattern, str)
                    and pattern.strip()
                    and not (motion_mode == "semantic-motion" and pattern.strip() in BASELINE_ONLY_PATTERNS)
                    and isinstance(actors, list)
                    and actors
                ):
                    qualifying_motion_cards += 1

        layout = card.get("layout")
        if component in STAGED_COMPONENTS and not isinstance(layout, dict):
            errors.append(f"{cid}: staged component requires layout.heightPx and layout.verticalGapsPx")
        if isinstance(layout, dict):
            height = as_number(layout.get("heightPx"))
            if height is None or not 180 <= height <= 292:
                errors.append(f"{cid}: layout.heightPx must be within 180-292")
            gaps = layout.get("verticalGapsPx")
            if component in STAGED_COMPONENTS and (not isinstance(gaps, list) or not gaps):
                errors.append(f"{cid}: staged component requires non-empty layout.verticalGapsPx")
            elif isinstance(gaps, list):
                for gap_index, gap_value in enumerate(gaps, 1):
                    gap = as_number(gap_value)
                    if gap is None or gap < 0:
                        errors.append(f"{cid}: vertical gap {gap_index} must be a non-negative number")
                    elif gap > 36:
                        errors.append(f"{cid}: vertical gap {gap_index} exceeds the hard 36px limit")
                    elif gap < 16 or gap > 32:
                        warnings.append(f"{cid}: vertical gap {gap_index} is outside the preferred 16-32px range")

        events = card.get("events")
        if not isinstance(events, list) or not events:
            errors.append(f"{cid}: card must contain events")
            continue
        cue_texts: list[str] = []
        event_starts: list[float] = []
        for event_index, event in enumerate(events, 1):
            if not isinstance(event, dict):
                errors.append(f"{cid}: event {event_index} must be an object")
                continue
            cue = event.get("cueText")
            if not isinstance(cue, str) or not cue.strip():
                errors.append(f"{cid}: event {event_index} is missing cueText")
            else:
                cue_texts.append(cue.strip())
            for field in ("target", "event"):
                if not isinstance(event.get(field), str) or not event[field].strip():
                    errors.append(f"{cid}: event {event_index} is missing {field}")
            event_start = as_number(event.get("start"))
            if event_start is None:
                errors.append(f"{cid}: event {event_index} is missing a numeric start")
            elif event_start < start - 1e-6 or event_start > end + 1e-6:
                errors.append(f"{cid}: event {event_index} start falls outside the card interval")
            else:
                event_starts.append(event_start)
        if event_starts and abs(min(event_starts) - start) > 0.10 + 1e-6:
            errors.append(f"{cid}: first event must begin within 3 frames of card start")

        semantic_mode = card.get("semanticMode")
        if semantic_mode is not None and semantic_mode not in SEMANTIC_MODES:
            errors.append(f"{cid}: semanticMode must be one of {sorted(SEMANTIC_MODES)}")
        if semantic_mode == "explain":
            items = card.get("displayItems")
            if not isinstance(items, list) or not 3 <= len(items) <= 6:
                errors.append(f"{cid}: explain cards require 3-6 displayItems")
            else:
                normalized_cues = {normalized_text(cue) for cue in cue_texts}
                for item_index, item in enumerate(items, 1):
                    if not isinstance(item, str) or not item.strip():
                        errors.append(f"{cid}: displayItems item {item_index} must be non-empty text")
                        continue
                    normalized_item = normalized_text(item)
                    if NONSTANDARD_ZERO_TO_ONE.search(item):
                        errors.append(f"{cid}: display item '{item}' must use 0~1 for the zero-to-one range")
                    if normalized_item in normalized_cues:
                        errors.append(f"{cid}: display item '{item}' merely repeats a complete cueText")
                    if len(normalized_item) > 8:
                        warnings.append(f"{cid}: display item '{item}' is longer than the preferred 8 characters")
                for event_index, event in enumerate(events, 1):
                    if isinstance(event, dict) and "displayItems" in event and event["displayItems"] != items:
                        errors.append(f"{cid}: event {event_index} displayItems must match the card-level displayItems")

        for display_field in ("title", "detail", "label", "text", "question"):
            display_value = card.get(display_field)
            if isinstance(display_value, str) and NONSTANDARD_ZERO_TO_ONE.search(display_value):
                errors.append(f"{cid}: {display_field} must use 0~1 for the zero-to-one range")

    slots = {item[3] for item in card_ranges}
    for slot in slots:
        slot_ranges = sorted((item for item in card_ranges if item[3] == slot), key=lambda item: (item[1], item[2]))
        for previous, current in zip(slot_ranges, slot_ranges[1:]):
            if overlaps(previous[1], previous[2], current[1], current[2]):
                errors.append(
                    f"{previous[0]} and {current[0]} overlap in visualSlot '{slot}'; states in one slot must hand off without overlap"
                )

    for index, caption in enumerate(captions, 1):
        cid = str(caption.get("id") or f"caption-{index}")
        if cid in caption_ids:
            errors.append(f"{cid}: duplicate caption id")
        caption_ids.add(cid)

        start = as_number(caption.get("start"))
        end = as_number(caption.get("end"))
        if start is None or end is None or end <= start:
            errors.append(f"{cid}: invalid caption start/end")
            continue
        caption_ranges.append((cid, start, end))
        if end - start < 0.35 - 1e-6:
            errors.append(f"{cid}: caption duration is shorter than 0.35s")

        text = caption.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{cid}: missing display text")
            continue
        text = text.strip()
        caption_entries.append((cid, start, end, text))
        equivalent_em = caption_equivalent_em(text)
        if equivalent_em > CAPTION_MAX_EQUIVALENT_EM + 1e-6:
            errors.append(
                f"{cid}: caption is {equivalent_em:.2f} full-width equivalents; split at a semantic/natural breath boundary"
            )
        if FORBIDDEN_PUNCTUATION.search(text):
            errors.append(f"{cid}: display text contains punctuation other than a question mark: {text}")
        if text in ISOLATED_FILLERS:
            errors.append(f"{cid}: isolated filler must not become a caption: {text}")
        if NONSTANDARD_ZERO_TO_ONE.search(text):
            errors.append(f"{cid}: zero-to-one range must be displayed as 0~1")

        source = caption.get("sourceText")
        if not isinstance(source, str) or not source.strip():
            message = f"{cid}: missing sourceText, so transcript fidelity cannot be audited"
            (errors if strict else warnings).append(message)
        else:
            validate_display_edits(cid, source.strip(), text, caption.get("displayEdits"), errors)
            approved_removals = caption.get("userApprovedProtectedRemovals", [])
            if not isinstance(approved_removals, list) or not all(isinstance(item, str) and item for item in approved_removals):
                errors.append(f"{cid}: userApprovedProtectedRemovals must be a list of non-empty strings")
                approved_removals = []
            for term in PROTECTED_TERMS:
                if term in source and term not in text and term not in approved_removals:
                    errors.append(f"{cid}: protected term '{term}' was removed from sourceText")

        keywords = caption.get("keywords", [])
        if not isinstance(keywords, list):
            errors.append(f"{cid}: keywords must be a list")
        else:
            if len(keywords) > 1:
                errors.append(f"{cid}: at most one continuous keyword phrase is allowed")
            if keywords:
                keyword = str(keywords[0])
                if keyword not in text:
                    errors.append(f"{cid}: keyword '{keyword}' is not present in display text")
                elif len(keyword) / max(len(text), 1) > 0.40 + 1e-6:
                    warnings.append(f"{cid}: keyword exceeds the preferred 40% of the caption")

        placement = caption.get("placement")
        if placement not in ALLOWED_PLACEMENTS:
            errors.append(f"{cid}: placement must be plain or with-card")
            continue

        overlapping_cards = [name for name, cs, ce, _slot in card_ranges if overlaps(start, end, cs, ce)]
        expected = "with-card" if overlapping_cards else "plain"
        if placement != expected:
            errors.append(f"{cid}: placement is {placement}, expected {expected}")
        for name, boundary_start, boundary_end, _slot in card_ranges:
            for boundary_name, boundary in (("start", boundary_start), ("end", boundary_end)):
                if start + 1e-6 < boundary < end - 1e-6:
                    errors.append(f"{cid}: {name} {boundary_name} boundary falls inside the caption; split it to prevent a position jump")

    sorted_caption_ranges = sorted(caption_ranges, key=lambda item: (item[1], item[2]))
    for previous, current in zip(sorted_caption_ranges, sorted_caption_ranges[1:]):
        if overlaps(previous[1], previous[2], current[1], current[2]):
            errors.append(f"{previous[0]} and {current[0]} overlap; only one caption may be visible at a time")

    sorted_caption_entries = sorted(caption_entries, key=lambda item: (item[1], item[2]))
    for previous, current in zip(sorted_caption_entries, sorted_caption_entries[1:]):
        validate_caption_boundary(previous[0], previous[3], current[0], current[3], errors)

    static_only_approved = bool(
        isinstance(motion_policy, dict) and motion_policy.get("staticOnlyApproved") is True
    )
    if len(cards) >= 6 and qualifying_motion_cards == 0 and not static_only_approved:
        errors.append(
            "package: card-heavy video has zero qualifying semantic-motion or b-roll cards; "
            "run the motion-opportunity scan or record user-approved motionPolicy.staticOnlyApproved"
        )

    return errors, warnings


def self_test() -> int:
    valid_captions = [
        {
            "id": "cap-01",
            "start": 0.0,
            "end": 1.0,
            "sourceText": "所以你自己想想看",
            "text": "所以你自己想想看",
            "keywords": ["想想看"],
            "placement": "plain",
        },
        {
            "id": "cap-02",
            "start": 1.0,
            "end": 2.0,
            "sourceText": "你觉得可能吗",
            "text": "你觉得可能吗？",
            "keywords": [],
            "placement": "with-card",
        },
        {
            "id": "cap-03",
            "start": 2.0,
            "end": 3.0,
            "sourceText": "从零到一的过程",
            "text": "从0~1的过程",
            "displayEdits": [{"from": "零到一", "to": "0~1", "reason": "numeric-style"}],
            "keywords": [],
            "placement": "plain",
        },
    ]
    valid_cards = [
        {
            "id": "card-01",
            "component": "title-detail",
            "purpose": "conclusion",
            "understandingGain": "shows one concept splitting into visible components instead of repeating the caption",
            "whyNow": "starts when the spoken explanation introduces the components, not during the opening question",
            "semanticMode": "explain",
            "displayItems": ["组成", "关系", "结果"],
            "start": 1.0,
            "end": 2.0,
            "layout": {"heightPx": 200, "verticalGapsPx": [24]},
            "motionPlan": {
                "mode": "semantic-motion",
                "semanticIntent": "information splits into three components",
                "pattern": "split",
                "actors": ["information token", "component nodes"],
                "motionGain": "the split makes the one-to-many structure visible",
            },
            "events": [
                {
                    "target": "title",
                    "event": "enter-center",
                    "cueText": "你觉得可能吗",
                    "start": 1.0,
                    "displayItems": ["组成", "关系", "结果"],
                }
            ],
        }
    ]
    errors, warnings = validate(valid_captions, valid_cards, strict=True)
    if errors or warnings:
        print("self-test valid fixture failed", errors, warnings, file=sys.stderr)
        return 1

    custom_card = json.loads(json.dumps(valid_cards[0]))
    custom_card["id"] = "card-custom-visual"
    custom_card["component"] = "dynamic-system-map"
    custom_card["visualModel"] = "experience tokens enter a shared system and become reusable team actions"
    custom_card["whyThisVisual"] = "shows the change from personal knowledge to reusable organizational capability"
    custom_card["motionPlan"] = {
        "mode": "semantic-motion",
        "semanticIntent": "personal experience becomes reusable organizational capability",
        "pattern": "experience-to-system",
        "actors": ["experience tokens", "shared system", "team actions"],
        "motionGain": "token ownership visibly changes from one person to the shared system",
    }
    errors, warnings = validate([], [custom_card], strict=True)
    if errors or warnings:
        print("self-test custom-component fixture failed", errors, warnings, file=sys.stderr)
        return 1

    undocumented_custom = dict(custom_card, id="card-undocumented-custom", component="metric-metaphor")
    undocumented_custom.pop("visualModel")
    undocumented_custom.pop("whyThisVisual")
    errors, _ = validate([], [undocumented_custom], strict=True)
    if not any("visualModel" in error for error in errors) or not any("whyThisVisual" in error for error in errors):
        print("self-test undocumented custom component unexpectedly passed", file=sys.stderr)
        return 1

    zero_gain_card = json.loads(json.dumps(valid_cards[0]))
    zero_gain_card["id"] = "card-zero-gain"
    zero_gain_card["understandingGain"] = "丰富画面"
    errors, _ = validate([], [zero_gain_card], strict=True)
    if not any("understandingGain" in error for error in errors):
        print("self-test generic understandingGain fixture unexpectedly passed", file=sys.stderr)
        return 1

    no_motion_gain = json.loads(json.dumps(valid_cards[0]))
    no_motion_gain["id"] = "card-no-motion-gain"
    no_motion_gain["motionPlan"].pop("motionGain")
    errors, _ = validate([], [no_motion_gain], strict=True)
    if not any("motionGain" in error for error in errors):
        print("self-test missing motionGain fixture unexpectedly passed", file=sys.stderr)
        return 1

    invalid_captions = [dict(valid_captions[0], text="你自己想想看。")]
    errors, _ = validate(invalid_captions, [], strict=True)
    if not errors:
        print("self-test invalid fixture unexpectedly passed", file=sys.stderr)
        return 1

    swallowed_caption = [dict(valid_captions[0], text="你想想看")]
    errors, _ = validate(swallowed_caption, [], strict=True)
    if not errors:
        print("self-test swallowed-caption fixture unexpectedly passed", file=sys.stderr)
        return 1

    def boundary_fixture(left: str, right: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "boundary-left",
                "start": 0.0,
                "end": 1.0,
                "sourceText": left,
                "text": left,
                "keywords": [],
                "placement": "plain",
            },
            {
                "id": "boundary-right",
                "start": 1.0,
                "end": 2.0,
                "sourceText": right,
                "text": right,
                "keywords": [],
                "placement": "plain",
            },
        ]

    invalid_boundaries = [
        ("团队里面执行强的人往", "往不一定适合做负责人", "atomic term '往往'"),
        ("然后第二个就是他", "一定要去能够跨部门的工作", "trailing pronoun '他'"),
        ("因为新媒体部门他", "不是一个孤立的部门", "trailing pronoun '他'"),
    ]
    for left, right, expected_error in invalid_boundaries:
        errors, _ = validate(boundary_fixture(left, right), [], strict=True)
        if not any(expected_error in error for error in errors):
            print(f"self-test invalid boundary unexpectedly passed: {left} | {right}", file=sys.stderr)
            return 1

    valid_boundaries = [
        ("团队里面执行强的人", "往往不一定适合做负责人"),
        ("然后第二个就是", "他一定要去能够跨部门的工作"),
        ("因为新媒体部门", "他不是一个孤立的部门"),
    ]
    for left, right in valid_boundaries:
        errors, warnings = validate(boundary_fixture(left, right), [], strict=True)
        if errors or warnings:
            print(f"self-test valid boundary failed: {left} | {right}", errors, warnings, file=sys.stderr)
            return 1
    invalid_cards = [
        {
            "id": "card-repeat",
            "purpose": "relation",
            "semanticMode": "explain",
            "displayItems": ["稳定生产环境"],
            "start": 0.0,
            "end": 1.0,
            "events": [{"cueText": "稳定生产环境"}],
        }
    ]
    errors, _ = validate([], invalid_cards, strict=True)
    if not errors:
        print("self-test repeated-cue fixture unexpectedly passed", file=sys.stderr)
        return 1


    overlap_card = dict(valid_cards[0], id="card-02", start=1.5, end=2.5)
    overlap_card["events"] = [dict(valid_cards[0]["events"][0], start=1.5)]
    errors, _ = validate([], [valid_cards[0], overlap_card], strict=True)
    if not errors:
        print("self-test overlapping-card fixture unexpectedly passed", file=sys.stderr)
        return 1

    loose_card = dict(valid_cards[0], id="card-loose", layout={"heightPx": 252, "verticalGapsPx": [64]})
    errors, _ = validate([], [loose_card], strict=True)
    if not errors:
        print("self-test loose-layout fixture unexpectedly passed", file=sys.stderr)
        return 1
    baseline_motion_card = dict(
        valid_cards[0],
        id="card-baseline-motion",
        motionPlan={
            "mode": "semantic-motion",
            "semanticIntent": "show the card",
            "pattern": "card-enter",
            "actors": ["card"],
        },
    )
    errors, _ = validate([], [baseline_motion_card], strict=True)
    if not errors:
        print("self-test baseline-motion fixture unexpectedly passed", file=sys.stderr)
        return 1
    static_cards = []
    for index in range(6):
        card = json.loads(json.dumps(valid_cards[0]))
        card["id"] = f"card-static-{index + 1}"
        card["start"] = float(index)
        card["end"] = float(index) + 0.9
        card["events"][0]["start"] = float(index)
        card["motionPlan"] = {
            "mode": "static",
            "semanticIntent": "single conclusion",
            "reason": "motion would not add understanding",
        }
        static_cards.append(card)
    errors, _ = validate([], static_cards, strict=True)
    if not any("zero qualifying" in error for error in errors):
        print("self-test zero-motion guard unexpectedly passed", file=sys.stderr)
        return 1
    errors, warnings = validate(
        [],
        static_cards,
        strict=True,
        motion_policy={"staticOnlyApproved": True, "reason": "user explicitly requested static cards"},
    )
    if errors or warnings:
        print("self-test approved-static fixture failed", errors, warnings, file=sys.stderr)
        return 1
    print("Self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captions", type=Path)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.captions is None or args.timeline is None:
        parser.error("--captions and --timeline are required unless --self-test is used")

    try:
        captions = captions_list(load_json(args.captions))
        timeline_payload = load_json(args.timeline)
        cards = cards_list(timeline_payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    motion_policy = timeline_payload.get("motionPolicy") if isinstance(timeline_payload, dict) else None
    errors, warnings = validate(captions, cards, strict=args.strict, motion_policy=motion_policy)
    for item in warnings:
        print(f"[WARN] {item}")
    for item in errors:
        print(f"[ERROR] {item}")
    print(f"Checked {len(captions)} captions and {len(cards)} cards: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
