#!/usr/bin/env python3
"""Deterministic run manifest helper for the v2.7 listing pipeline."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HARD_REJECT_REASONS = {"api_error", "file_corrupt", "off_topic", "safety_placeholder", "unrecognizable"}
RETRYABLE_CODES = {"rate_limit", "server_error", "timeout", "network_error", "provider_json_error"}
QA_LABELS = {"green", "yellow", "red"}


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
        "schema_version": 2,
        "created_at": now(),
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
            if label in {"green", "yellow"}:
                deliverable_slots.append(n)
        elif status == "rejected" and label == "red" and reason in HARD_REJECT_REASONS:
            rejected_slots.append(n)

    if delivery:
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
        for n in deliverable_slots:
            token = tokens.get(str(n), {})
            if not token.get("file_token") or not token.get("image_key"):
                errors.append(f"slot {n}: both file_token and image_key required for delivery")
        for n in rejected_slots:
            token = tokens.get(str(n), {})
            if token.get("file_token") or token.get("image_key"):
                errors.append(f"slot {n}: hard-rejected slot must not have delivery tokens")

        docx = delivery_state.get("docx") or {}
        folder = delivery_state.get("folder") or {}
        if not docx.get("token") or not docx.get("permalink"):
            errors.append("delivery docx token and permalink required")
        if not folder.get("permalink"):
            errors.append("delivery folder permalink required")
        # This schema always represents the nine-image pipeline.  A copy-only
        # manifest may use a separate future shape and omit card evidence.
        card = delivery_state.get("card") or {}
        if card.get("send_success") is not True or not card.get("message_id"):
            errors.append("nine-image delivery requires card send_success true and message_id")
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
    init.set_defaults(func=cmd_init)
    timing = sub.add_parser("timing", help="record a stage duration")
    timing.add_argument("manifest")
    timing.add_argument("stage")
    timing.add_argument("--seconds", required=True, type=float)
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
