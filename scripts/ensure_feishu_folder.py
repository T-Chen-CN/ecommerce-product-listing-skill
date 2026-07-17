#!/usr/bin/env python3
"""Idempotent Feishu folder ensure helper for the Listing Skill.

Contract:

* Identity for each directory layer is the pair ``(parent_token, exact_name)``.
* The helper lists **all** direct children of ``parent_token`` (paginating until
  ``has_more`` is false), and considers a candidate only when ``type == "folder"``
  and ``name`` is byte-for-byte equal to the target name.
* Decision by exact-match count:
    - ``count == 1``: reuse; the create adapter must not be called.
    - ``count == 0``: acquire a cross-process file lock keyed on
      ``sha256(parent_token + \x00 + name)``, run a **second** full listing;
      if that is still 0, call the create adapter, then run a **third** full
      listing that must return exactly one exact match whose token equals the
      token returned by create.
    - ``count > 1`` at any stage: hard-fail with duplicate-folder evidence.
* Pagination is bounded (`MAX_PAGES = 100`) and rejects loops via a seen-set of
  page tokens. Malformed responses (non-dict, missing ``files``, non-list files,
  entries that are not dicts) are hard failures.
* The helper never deletes, moves, merges, or picks a canonical folder from
  duplicates.
* The evidence dict is JSON serialisable and uses the same field names required
  by ``scripts/run_manifest.py`` schema v7:
  ``resolution``, ``exact_match_count_first/second/after``, ``created``,
  ``created_token``, ``pages_scanned_first/second/after``, ``resolved_at`` (an
  ISO 8601 timestamp that includes an explicit timezone offset), plus
  ``name``, ``type``, ``token``, ``parent_token``.
* CLI: on success stdout receives one line of JSON (the evidence dict); on
  failure the process exits non-zero and writes a JSON error object to stderr.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

MAX_PAGES = 100
LOCK_DIR = Path(os.environ.get("ENSURE_FEISHU_LOCK_DIR", tempfile.gettempdir())) / "ecommerce-listing-folder-locks"


class EnsureFolderError(RuntimeError):
    """Raised when the ensure-folder contract cannot be satisfied."""

    def __init__(self, code: str, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": str(self), "details": self.details}}


@dataclass
class Adapter:
    """Injectable IO adapter.

    - ``list_children(parent_token, page_token)`` must return a dict shaped like
      ``{"files": [{"name": str, "type": str, "token": str}, ...],
         "has_more": bool, "next_page_token": Optional[str]}``.
      ``page_token`` is ``None`` for the first page.
    - ``create_folder(parent_token, name)`` must return a dict shaped like
      ``{"token": str}``.
    Any adapter that raises is treated as a hard failure.
    """

    list_children: Callable[[str, Optional[str]], Dict[str, Any]]
    create_folder: Callable[[str, str], Dict[str, Any]]


# ---------------------------------------------------------------------------
# Core helpers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock_path(parent_token: str, name: str) -> Path:
    key = hashlib.sha256((parent_token + "\x00" + name).encode("utf-8")).hexdigest()
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    return LOCK_DIR / f"{key}.lock"


def _validate_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnsureFolderError("invalid_argument", f"{field} must be a non-empty string")
    return value


def _list_all(adapter: Adapter, parent_token: str) -> Tuple[List[Dict[str, Any]], int]:
    """Return (all_files, pages_scanned). Raises on malformed responses or loops."""
    seen_tokens: set = set()
    all_files: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    pages = 0
    while True:
        pages += 1
        if pages > MAX_PAGES:
            raise EnsureFolderError(
                "pagination_overflow",
                f"exceeded MAX_PAGES={MAX_PAGES} while listing {parent_token!r}",
            )
        try:
            resp = adapter.list_children(parent_token, page_token)
        except EnsureFolderError:
            raise
        except Exception as exc:  # pragma: no cover - adapter contract
            raise EnsureFolderError("adapter_error", f"list_children raised: {exc!r}") from exc
        if not isinstance(resp, dict):
            raise EnsureFolderError("malformed_response", "list_children must return a dict")
        files = resp.get("files")
        if not isinstance(files, list):
            raise EnsureFolderError("malformed_response", "list_children response must have list 'files'")
        for entry in files:
            if not isinstance(entry, dict):
                raise EnsureFolderError("malformed_response", "list_children file entries must be dicts")
            if "name" not in entry or "type" not in entry or "token" not in entry:
                raise EnsureFolderError(
                    "malformed_response",
                    "list_children file entries must have name/type/token",
                )
        all_files.extend(files)
        if not resp.get("has_more"):
            break
        next_token = resp.get("next_page_token")
        if not isinstance(next_token, str) or not next_token:
            raise EnsureFolderError(
                "malformed_response",
                "has_more=true requires non-empty next_page_token",
            )
        if next_token in seen_tokens:
            raise EnsureFolderError("pagination_loop", f"page_token {next_token!r} repeated")
        seen_tokens.add(next_token)
        page_token = next_token
    return all_files, pages


def _exact_matches(files: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    return [
        f
        for f in files
        if f.get("type") == "folder" and isinstance(f.get("name"), str) and f["name"] == name
    ]


# ---------------------------------------------------------------------------
# Public API


def ensure_folder(adapter: Adapter, parent_token: str, name: str) -> Dict[str, Any]:
    """Ensure the folder ``name`` exists under ``parent_token`` exactly once.

    Returns the JSON-serialisable evidence dict. Raises ``EnsureFolderError``
    on any contract violation.
    """
    parent_token = _validate_string(parent_token, "parent_token")
    name = _validate_string(name, "name")

    lock_file = _lock_path(parent_token, name)
    lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        # First listing.
        files_first, pages_first = _list_all(adapter, parent_token)
        matches_first = _exact_matches(files_first, name)
        if len(matches_first) > 1:
            raise EnsureFolderError(
                "duplicate_folder",
                f"multiple folders named {name!r} already exist under {parent_token!r}",
                {"stage": "first", "candidates": [_candidate(f) for f in matches_first]},
            )
        if len(matches_first) == 1:
            token = matches_first[0]["token"]
            return _evidence(
                name=name,
                token=token,
                parent_token=parent_token,
                resolution="reused",
                exact_match_count_first=1,
                pages_scanned_first=pages_first,
            )

        # Zero matches: run a second listing before creating.
        files_second, pages_second = _list_all(adapter, parent_token)
        matches_second = _exact_matches(files_second, name)
        if len(matches_second) > 1:
            raise EnsureFolderError(
                "duplicate_folder",
                f"multiple folders named {name!r} appeared during second listing under {parent_token!r}",
                {"stage": "second", "candidates": [_candidate(f) for f in matches_second]},
            )
        if len(matches_second) == 1:
            token = matches_second[0]["token"]
            # A concurrent actor created the folder between the two listings.
            # Reuse it and record the discovery via pages_scanned_second.
            return _evidence(
                name=name,
                token=token,
                parent_token=parent_token,
                resolution="reused",
                exact_match_count_first=0,
                pages_scanned_first=pages_first,
                exact_match_count_second=1,
                pages_scanned_second=pages_second,
            )

        # Still zero: create.
        try:
            create_resp = adapter.create_folder(parent_token, name)
        except EnsureFolderError:
            raise
        except Exception as exc:  # pragma: no cover - adapter contract
            raise EnsureFolderError("adapter_error", f"create_folder raised: {exc!r}") from exc
        if not isinstance(create_resp, dict):
            raise EnsureFolderError("malformed_response", "create_folder must return a dict")
        created_token = create_resp.get("token")
        if not isinstance(created_token, str) or not created_token:
            raise EnsureFolderError("malformed_response", "create_folder must return non-empty token")

        # Post-create verification listing.
        files_after, pages_after = _list_all(adapter, parent_token)
        matches_after = _exact_matches(files_after, name)
        if len(matches_after) != 1:
            raise EnsureFolderError(
                "create_verification_failed",
                f"expected exactly one folder named {name!r} after create, saw {len(matches_after)}",
                {"stage": "after", "candidates": [_candidate(f) for f in matches_after]},
            )
        if matches_after[0]["token"] != created_token:
            raise EnsureFolderError(
                "create_token_mismatch",
                "unique post-create folder token does not match create_folder response token",
                {
                    "created_token": created_token,
                    "observed_token": matches_after[0]["token"],
                },
            )
        return _evidence(
            name=name,
            token=created_token,
            parent_token=parent_token,
            resolution="created",
            exact_match_count_first=0,
            pages_scanned_first=pages_first,
            exact_match_count_second=0,
            pages_scanned_second=pages_second,
            exact_match_count_after=1,
            pages_scanned_after=pages_after,
            created=True,
            created_token=created_token,
        )
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def _candidate(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": entry.get("name"), "token": entry.get("token"), "type": entry.get("type")}


def _evidence(
    *,
    name: str,
    token: str,
    parent_token: str,
    resolution: str,
    exact_match_count_first: int,
    pages_scanned_first: int,
    exact_match_count_second: Optional[int] = None,
    pages_scanned_second: Optional[int] = None,
    exact_match_count_after: Optional[int] = None,
    pages_scanned_after: Optional[int] = None,
    created: bool = False,
    created_token: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "name": name,
        "type": "folder",
        "token": token,
        "parent_token": parent_token,
        "resolution": resolution,
        "exact_match_count_first": exact_match_count_first,
        "exact_match_count_second": exact_match_count_second,
        "exact_match_count_after": (1 if resolution == "reused" and exact_match_count_after is None else exact_match_count_after),
        "created": created,
        "created_token": created_token,
        "pages_scanned_first": pages_scanned_first,
        "pages_scanned_second": pages_scanned_second,
        "pages_scanned_after": (pages_scanned_first if resolution == "reused" and pages_scanned_after is None else pages_scanned_after),
        "resolved_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Adapters


class SubprocessJSONAdapter:
    """Adapter that shells out to a user-supplied command and reads JSON on stdout.

    The command receives the operation and its arguments as extra ``argv``
    entries: ``[<command...>, "list-children", parent_token, page_token?]`` and
    ``[<command...>, "create-folder", parent_token, name]``. This lets callers
    plug in any Feishu CLI without hard-coding provider-specific flags.
    """

    def __init__(self, command: List[str], env: Optional[Dict[str, str]] = None, timeout: float = 60.0) -> None:
        if not command:
            raise EnsureFolderError("invalid_argument", "command must be non-empty")
        self.command = list(command)
        self.env = env
        self.timeout = timeout

    def list_children(self, parent_token: str, page_token: Optional[str]) -> Dict[str, Any]:
        argv = self.command + ["list-children", parent_token]
        if page_token is not None:
            argv.append(page_token)
        return self._run(argv)

    def create_folder(self, parent_token: str, name: str) -> Dict[str, Any]:
        argv = self.command + ["create-folder", parent_token, name]
        return self._run(argv)

    def _run(self, argv: List[str]) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=self.env,
                check=False,
            )
        except FileNotFoundError as exc:
            raise EnsureFolderError("adapter_error", f"command not found: {argv[0]}") from exc
        if result.returncode != 0:
            raise EnsureFolderError(
                "adapter_error",
                f"command exited {result.returncode}: {' '.join(argv)}",
                {"stderr": result.stderr[-4000:]},
            )
        stdout = result.stdout.strip()
        if not stdout:
            raise EnsureFolderError("adapter_error", "command produced empty stdout")
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise EnsureFolderError("adapter_error", f"command stdout is not valid JSON: {exc}") from exc


def load_adapter_from_module(spec: str) -> Adapter:
    """Load ``module:factory`` where ``factory()`` returns an :class:`Adapter`."""
    if ":" not in spec:
        raise EnsureFolderError("invalid_argument", "--adapter-module must be 'module:factory'")
    module_name, factory_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    adapter = factory()
    if not isinstance(adapter, Adapter):
        raise EnsureFolderError("invalid_argument", "adapter factory must return an Adapter")
    return adapter


# ---------------------------------------------------------------------------
# CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ensure a Feishu folder exists exactly once under a parent.",
    )
    parser.add_argument("--parent-token", required=True)
    parser.add_argument("--name", required=True)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--adapter-module", help="module:factory returning an Adapter")
    src.add_argument("--subprocess-command", nargs="+", help="command that speaks the ensure-folder subprocess protocol")
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.adapter_module:
            adapter = load_adapter_from_module(args.adapter_module)
        else:
            adapter = SubprocessJSONAdapter(args.subprocess_command, timeout=args.timeout)
            # Wrap into the Adapter dataclass for a uniform contract.
            adapter = Adapter(
                list_children=adapter.list_children,
                create_folder=adapter.create_folder,
            )
        evidence = ensure_folder(adapter, args.parent_token, args.name)
        sys.stdout.write(json.dumps(evidence, ensure_ascii=False) + "\n")
        return 0
    except EnsureFolderError as exc:
        sys.stderr.write(json.dumps(exc.to_dict(), ensure_ascii=False) + "\n")
        return 2
    except Exception as exc:  # pragma: no cover - unexpected
        sys.stderr.write(json.dumps({"error": {"code": "unexpected", "message": repr(exc)}}) + "\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
