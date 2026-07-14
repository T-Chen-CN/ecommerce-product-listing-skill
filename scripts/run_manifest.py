#!/usr/bin/env python3
"""Deterministic run manifest helper for the v2.7 listing pipeline."""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HARD_REJECT_REASONS = {"api_error", "file_corrupt", "off_topic", "safety_placeholder", "unrecognizable"}
RETRYABLE_CODES = {"rate_limit", "server_error", "timeout", "network_error", "provider_json_error"}
QA_LABELS = {"green", "yellow", "red"}
TIMING_STAGES = ("wave_0", "wave_1", "wave_2", "total")


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_init(args):
    data = {
        "schema_version": 3,
        "created_at": now(),
        "delivery_mode": args.delivery_mode,
        "facts": {"market": args.market, "platform": args.platform, "category": args.category},
        "modules": [],
        "images": [{"slot": n, "status": "pending", "file": None, "provider_error": None,
                    "qa_label": None, "hard_reject_reason": None} for n in range(1, 10)],
        "qa": {"mode": "nine-image-single-round", "reviewed_at": None},
        "tokens": {},
        "delivery": {
            "deliverable_slots": [],
            "rejected_slots": [],
            "docx": {"token": None, "permalink": None},
            "folder": {"permalink": None},
            "card": {"message_id": None, "send_success": False},
        },
        "timings": {},
        "status": "initialized",
    }
    save(args.manifest, data)


def cmd_timing(args):
    data = load(args.manifest)
    data["timings"][args.stage] = {"seconds": args.seconds, "recorded_at": now()}
    save(args.manifest, data)


def nonnegative_finite_float(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("seconds must be finite and >= 0")
    return number


def cmd_select_retry(args):
    data = load(args.manifest)
    slots = []
    for image in data["images"]:
        error = image.get("provider_error") or {}
        # The provider's structured code is authoritative.  A stale or forged
        # retryable boolean must neither enable nor disable a known mapping.
        if image.get("status") == "failed" and error.get("code") in RETRYABLE_CODES:
            slots.append(image["slot"])
    print(json.dumps({"slots": slots}))


def is_readable_regular_file(value):
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    try:
        if not path.is_file():
            return False
        with path.open("rb") as handle:
            return handle.readable()
    except OSError:
        return False


def has_supported_image_magic(value):
    if not is_readable_regular_file(value):
        return False
    try:
        with Path(value).open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return False
    return (header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
            or (header.startswith(b"RIFF") and header[8:12] == b"WEBP")
            or header.startswith((b"GIF87a", b"GIF89a")))


def is_iso_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def is_conservative_identifier(value):
    # Feishu/Lark API families use different, evolving token prefixes.  Do not
    # invent a fixed prefix contract: require only plausible opaque evidence.
    return isinstance(value, str) and len(value) >= 6 and not any(char.isspace() for char in value)


def is_feishu_permalink(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    allowed = ("feishu.cn", "larksuite.com")
    return parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in allowed)


def validation_errors(data, delivery):
    errors = []
    slots = data.get("images", [])
    if [item.get("slot") for item in slots] != list(range(1, 10)):
        errors.append("images must contain slots 1..9 exactly once")

    deliverable_slots = []
    rejected_slots = []
    for image in slots:
        n = image.get("slot")
        status = image.get("status")
        label = image.get("qa_label")
        reason = image.get("hard_reject_reason")

        if label is not None and label not in QA_LABELS:
            errors.append(f"slot {n}: qa_label must be one of {sorted(QA_LABELS)}")
        if label == "red":
            if status != "rejected":
                errors.append(f"slot {n}: qa_label red requires status rejected")
            if reason not in HARD_REJECT_REASONS:
                errors.append(f"slot {n}: hard_reject_reason must be one of {sorted(HARD_REJECT_REASONS)}")
        elif status == "rejected":
            errors.append(f"slot {n}: status rejected requires qa_label red and a hard_reject_reason")
        elif reason:
            errors.append(f"slot {n}: hard_reject_reason requires qa_label red")
        if status in {"pending", "failed"} and label is not None:
            errors.append(f"slot {n}: status {status} requires qa_label null")
        if status not in {"pending", "failed", "success", "rejected"}:
            errors.append(f"slot {n}: unknown status {status!r}")

        if status == "success":
            if label not in {"green", "yellow"}:
                errors.append(f"slot {n}: status success requires qa_label green or yellow")
            if not is_readable_regular_file(image.get("file")):
                errors.append(f"slot {n}: delivery file must exist and be a readable regular file")
            elif not has_supported_image_magic(image.get("file")):
                errors.append(f"slot {n}: delivery file must have PNG/JPEG/WebP/GIF magic bytes")
            if label in {"green", "yellow"}:
                deliverable_slots.append(n)
        elif status == "rejected" and label == "red" and reason in HARD_REJECT_REASONS:
            rejected_slots.append(n)

    if delivery:
        for image in slots:
            if image.get("status") in {"pending", "failed"}:
                errors.append(f"slot {image.get('slot')}: status {image.get('status')} is not final for delivery")

        qa = data.get("qa") or {}
        if qa.get("mode") != "nine-image-single-round":
            errors.append("qa.mode must be exactly nine-image-single-round")
        if not is_iso_datetime(qa.get("reviewed_at")):
            errors.append("qa.reviewed_at must be a non-empty parseable ISO datetime")

        timings = data.get("timings") or {}
        timing_seconds = {}
        for stage in TIMING_STAGES:
            entry = timings.get(stage) or {}
            seconds = entry.get("seconds")
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
                errors.append(f"timings.{stage}.seconds must be finite and >= 0")
            else:
                timing_seconds[stage] = seconds
        if len(timing_seconds) == len(TIMING_STAGES) and any(
                timing_seconds["total"] < timing_seconds[stage] for stage in TIMING_STAGES[:-1]):
            errors.append("timings.total.seconds must be at least each wave duration")

        if data.get("status") != "ready":
            errors.append("delivery status must be ready")
        delivery_state = data.get("delivery") or {}
        if delivery_state.get("deliverable_slots") != deliverable_slots:
            errors.append("delivery.deliverable_slots must exactly match successful green/yellow slots")
        if delivery_state.get("rejected_slots") != rejected_slots:
            errors.append("delivery.rejected_slots must exactly match red hard-rejected slots")
        if set(deliverable_slots) & set(rejected_slots):
            errors.append("rejected slots cannot enter the deliverable set")

        tokens = data.get("tokens", {})
        if not isinstance(tokens, dict):
            errors.append("tokens must be an object")
            tokens = {}
        known_token_slots = {str(n) for n in range(1, 10)}
        for key in tokens:
            if key not in known_token_slots:
                errors.append(f"unknown token slot {key!r}")
        delivery_mode = data.get("delivery_mode")
        if delivery_mode not in {"docx", "card"}:
            errors.append("delivery_mode must be docx or card")
        for n in deliverable_slots:
            token = tokens.get(str(n), {})
            if not isinstance(token, dict):
                errors.append(f"slot {n}: token evidence must be an object")
                token = {}
            if not is_conservative_identifier(token.get("image_key")):
                errors.append(f"slot {n}: image_key required for {delivery_mode or 'delivery'} delivery")
                if token.get("image_key"):
                    errors.append(f"slot {n}: image_key must be non-whitespace and at least 6 characters")
            if delivery_mode == "docx" and not is_conservative_identifier(token.get("file_token")):
                errors.append(f"slot {n}: file_token required for docx delivery")
                if token.get("file_token"):
                    errors.append(f"slot {n}: file_token must be non-whitespace and at least 6 characters")
        for n in rejected_slots:
            token = tokens.get(str(n), {})
            if not isinstance(token, dict):
                errors.append(f"slot {n}: token evidence must be an object")
                token = {}
            if token.get("file_token") or token.get("image_key"):
                errors.append(f"slot {n}: hard-rejected slot must not have delivery tokens")

        docx = delivery_state.get("docx") or {}
        folder = delivery_state.get("folder") or {}
        if delivery_mode == "docx":
            if not docx.get("token") or not docx.get("permalink"):
                errors.append("delivery docx token and permalink required")
            if docx.get("token") and not is_conservative_identifier(docx.get("token")):
                errors.append("delivery docx token must be non-whitespace and at least 6 characters")
            if docx.get("permalink") and not is_feishu_permalink(docx.get("permalink")):
                errors.append("delivery docx permalink must be HTTPS on feishu.cn/larksuite.com or a subdomain")
            if not folder.get("permalink"):
                errors.append("delivery folder permalink required")
            elif not is_feishu_permalink(folder.get("permalink")):
                errors.append("delivery folder permalink must be HTTPS on feishu.cn/larksuite.com or a subdomain")
        elif delivery_mode == "card":
            has_file_token = any(isinstance(token, dict) and token.get("file_token") for token in tokens.values())
            if has_file_token or docx.get("token") or docx.get("permalink") or folder.get("permalink"):
                errors.append("card delivery must not retain docx or folder evidence")
        # This schema always represents the nine-image pipeline.  A copy-only
        # manifest may use a separate future shape and omit card evidence.
        card = delivery_state.get("card") or {}
        if card.get("send_success") is not True or not card.get("message_id"):
            errors.append("nine-image delivery requires card send_success true and message_id")
        elif not is_conservative_identifier(card.get("message_id")):
            errors.append("delivery card message_id must be non-whitespace and at least 6 characters")
    return errors


def cmd_validate(args):
    errors = validation_errors(load(args.manifest), args.delivery)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("manifest valid")
    return 0


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="initialize a nine-slot manifest")
    init.add_argument("manifest")
    init.add_argument("--market", default=None)
    init.add_argument("--platform", default=None)
    init.add_argument("--category", default=None)
    init.add_argument("--delivery-mode", choices=("docx", "card"), default="docx",
                      help="final delivery evidence contract (default: docx)")
    init.set_defaults(func=cmd_init)
    timing = sub.add_parser("timing", help="record a stage duration")
    timing.add_argument("manifest")
    timing.add_argument("stage", choices=TIMING_STAGES)
    timing.add_argument("--seconds", required=True, type=nonnegative_finite_float)
    timing.set_defaults(func=cmd_timing)
    retry = sub.add_parser("select-retry", help="print retryable failed slots as JSON")
    retry.add_argument("manifest")
    retry.set_defaults(func=cmd_select_retry)
    validate = sub.add_parser("validate", help="validate structure and QA/delivery boundaries")
    validate.add_argument("manifest")
    validate.add_argument("--delivery", action="store_true")
    validate.set_defaults(func=cmd_validate)
    return root


def main():
    args = parser().parse_args()
    result = args.func(args)
    raise SystemExit(result or 0)


if __name__ == "__main__":
    main()
