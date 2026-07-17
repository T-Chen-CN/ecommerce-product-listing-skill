#!/usr/bin/env python3
"""Persistent, credential-free Feishu delivery route configuration."""
import argparse
import fcntl
import json
import os
import stat
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
ROUTES = ("docx", "interactive_card")
SENSITIVE_FRAGMENTS = ("token", "secret", "password", "credential", "api_key", "apikey")
CONFIG_FIELDS = {"schema_version", "default_delivery_route", "bootstrap_evidence", "configured_at", "last_success_at", "invalidated_at", "invalidation_reason"}


def now():
    return datetime.now(timezone.utc).isoformat()


def config_path(args):
    value = getattr(args, "config", None) or os.environ.get("ECOMMERCE_LISTING_DELIVERY_CONFIG")
    if not value:
        raise ValueError("delivery config path required via --config or ECOMMERCE_LISTING_DELIVERY_CONFIG")
    return Path(value)


@contextmanager
def locked(path):
    lock = Path(str(path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def atomic_save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def contains_secret(value):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(fragment in normalized for fragment in SENSITIVE_FRAGMENTS) or contains_secret(child):
                return True
    elif isinstance(value, list):
        return any(contains_secret(child) for child in value)
    return False


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("delivery config must be a JSON object")
    extra = set(data) - CONFIG_FIELDS
    if extra:
        raise ValueError(f"delivery config has unknown fields: {sorted(extra)}")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported delivery config schema_version; expected {SCHEMA_VERSION}")
    if data.get("default_delivery_route") not in ROUTES:
        raise ValueError("default_delivery_route must be docx or interactive_card")
    if not isinstance(data.get("bootstrap_evidence"), dict) or contains_secret(data["bootstrap_evidence"]):
        raise ValueError("bootstrap_evidence must be a credential-free object")
    if not isinstance(data.get("configured_at"), str) or not data["configured_at"].strip():
        raise ValueError("configured_at must be non-empty")
    for field in ("last_success_at", "invalidated_at", "invalidation_reason"):
        if data.get(field) is not None and (not isinstance(data[field], str) or not data[field].strip()):
            raise ValueError(f"{field} must be a non-empty string or null")
    return data


def load_config(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("delivery config is missing; bootstrap required") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("delivery config is corrupt; bootstrap required") from exc
    return validate(data)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def cmd_bootstrap(args):
    path = config_path(args)
    try:
        evidence = json.loads(args.evidence_json)
    except json.JSONDecodeError as exc:
        raise ValueError("--evidence-json must be valid JSON") from exc
    if not isinstance(evidence, dict):
        raise ValueError("--evidence-json must be an object")
    if contains_secret(evidence):
        raise ValueError("bootstrap evidence must not contain tokens, secrets, passwords, credentials, or api keys")
    data = {"schema_version": SCHEMA_VERSION, "default_delivery_route": args.delivery_route, "bootstrap_evidence": evidence, "configured_at": now(), "last_success_at": None, "invalidated_at": None, "invalidation_reason": None}
    validate(data)
    with locked(path):
        atomic_save(path, data)
    emit(data)


def cmd_status(args):
    emit(load_config(config_path(args)))


def cmd_resolve(args):
    data = load_config(config_path(args))
    if data["invalidated_at"] is not None:
        raise ValueError("delivery config is invalidated; diagnose and bootstrap again")
    route = data["default_delivery_route"]
    source = "skill_config"
    override = None
    if args.override_route:
        confirmation = (args.user_confirmation or "").strip()
        if not confirmation:
            raise ValueError("explicit route override requires non-empty --user-confirmation")
        route = args.override_route
        source = "explicit_user_override"
        override = {"delivery_route": route, "confirmation_text": confirmation, "recorded_at": now()}
    emit({"delivery_route": route, "delivery_route_source": source, "delivery_config_schema_version": SCHEMA_VERSION, "delivery_override": override})


def mutate(args, callback):
    path = config_path(args)
    with locked(path):
        data = load_config(path)
        callback(data)
        validate(data)
        atomic_save(path, data)
    emit(data)


def cmd_record_success(args):
    def update(data):
        if data["invalidated_at"] is not None:
            raise ValueError("cannot record success for invalidated config")
        data["last_success_at"] = now()
    mutate(args, update)


def cmd_invalidate(args):
    reason = args.reason.strip()
    if not reason:
        raise ValueError("--reason must be non-empty")
    def update(data):
        data["invalidated_at"] = now()
        data["invalidation_reason"] = reason
    mutate(args, update)


def parser():
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("bootstrap", "status", "resolve", "record-success", "invalidate"):
        command = sub.add_parser(name)
        command.add_argument("--config")
    p = sub.choices["bootstrap"]
    p.add_argument("--delivery-route", choices=ROUTES, default="docx")
    p.add_argument("--evidence-json", default="{}")
    p.set_defaults(func=cmd_bootstrap)
    sub.choices["status"].set_defaults(func=cmd_status)
    p = sub.choices["resolve"]
    p.add_argument("--override-route", choices=ROUTES)
    p.add_argument("--user-confirmation")
    p.set_defaults(func=cmd_resolve)
    sub.choices["record-success"].set_defaults(func=cmd_record_success)
    p = sub.choices["invalidate"]
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_invalidate)
    return root


def main():
    try:
        args = parser().parse_args()
        args.func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
