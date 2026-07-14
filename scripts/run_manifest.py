#!/usr/bin/env python3
"""Deterministic run manifest helper for the v2.7 listing pipeline."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HARD_REJECT_REASONS = {"api_error", "file_corrupt", "off_topic", "safety_placeholder", "unrecognizable"}
RETRYABLE_CODES = {"rate_limit", "server_error", "timeout", "network_error", "provider_json_error"}


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
        "schema_version": 1,
        "created_at": now(),
        "facts": {"market": args.market, "platform": args.platform, "category": args.category},
        "modules": [],
        "images": [{"slot": n, "status": "pending", "file": None, "provider_error": None,
                    "qa_label": None, "hard_reject_reason": None} for n in range(1, 10)],
        "qa": {"mode": "nine-image-single-round", "reviewed_at": None},
        "tokens": {},
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
        retryable = error.get("retryable")
        if retryable is None:
            retryable = error.get("code") in RETRYABLE_CODES
        if image.get("status") == "failed" and retryable:
            slots.append(image["slot"])
    print(json.dumps({"slots": slots}))


def validation_errors(data, delivery):
    errors = []
    slots = data.get("images", [])
    if [item.get("slot") for item in slots] != list(range(1, 10)):
        errors.append("images must contain slots 1..9 exactly once")
    for image in slots:
        label = image.get("qa_label")
        reason = image.get("hard_reject_reason")
        if label == "red" and reason not in HARD_REJECT_REASONS:
            errors.append(f"slot {image.get('slot')}: hard_reject_reason must be one of {sorted(HARD_REJECT_REASONS)}")
        if label != "red" and reason:
            errors.append(f"slot {image.get('slot')}: hard_reject_reason requires qa_label red")
    if delivery:
        if data.get("status") != "ready":
            errors.append("delivery status must be ready")
        for image in slots:
            n = image.get("slot")
            if image.get("status") != "success" or not image.get("file") or not image.get("qa_label"):
                errors.append(f"slot {n}: successful file and qa_label required for delivery")
            token = data.get("tokens", {}).get(str(n), {})
            if not token.get("file_token") or not token.get("image_key"):
                errors.append(f"slot {n}: both file_token and image_key required for delivery")
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
