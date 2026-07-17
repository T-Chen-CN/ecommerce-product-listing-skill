"""Contract tests for scripts.ensure_feishu_folder."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ensure_feishu_folder import (  # noqa: E402
    Adapter,
    EnsureFolderError,
    LOCK_DIR,
    MAX_PAGES,
    SubprocessJSONAdapter,
    ensure_folder,
)


class RecordingAdapter:
    def __init__(
        self,
        list_pages: List[Dict[str, Any]],
        create_result: Optional[Dict[str, Any]] = None,
        list_pages_after_create: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.list_pages = list_pages
        self.create_result = create_result
        self.list_pages_after_create = list_pages_after_create
        self.list_calls: List[Optional[str]] = []
        self.create_calls: List[str] = []

    def list_children(self, parent_token: str, page_token: Optional[str]) -> Dict[str, Any]:
        self.list_calls.append(page_token)
        pool = self.list_pages_after_create if self.create_calls and self.list_pages_after_create else self.list_pages
        if page_token is None:
            return pool[0]
        for page in pool:
            if page.get("this_page_token") == page_token:
                return page
        raise AssertionError(f"unexpected page_token {page_token!r}")

    def create_folder(self, parent_token: str, name: str) -> Dict[str, Any]:
        self.create_calls.append(name)
        if not self.create_result:
            raise AssertionError("create_folder should not have been called")
        return self.create_result


def _page(files, has_more=False, next_page_token=None, this_page_token=None):
    return {
        "files": files,
        "has_more": has_more,
        "next_page_token": next_page_token,
        "this_page_token": this_page_token,
    }


def _tempfile_lock_dir(test: unittest.TestCase) -> Path:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    path = Path(tmp.name)
    # Rebind module-level LOCK_DIR to the temp directory to prevent parallel
    # tests from clobbering each other's locks.
    import scripts.ensure_feishu_folder as mod

    prev = mod.LOCK_DIR
    mod.LOCK_DIR = path
    test.addCleanup(lambda: setattr(mod, "LOCK_DIR", prev))
    return path


class EnsureFolderTests(unittest.TestCase):
    def setUp(self) -> None:
        _tempfile_lock_dir(self)

    def test_single_exact_match_is_reused_without_create(self) -> None:
        pages = [_page([{"name": "Listing", "type": "folder", "token": "tok-listing"}])]
        adapter = Adapter(RecordingAdapter(pages).list_children, RecordingAdapter(pages).create_folder)
        rec = RecordingAdapter(pages)
        adapter = Adapter(rec.list_children, rec.create_folder)
        ev = ensure_folder(adapter, "parent-1", "Listing")
        self.assertEqual(ev["resolution"], "reused")
        self.assertEqual(ev["token"], "tok-listing")
        self.assertEqual(ev["exact_match_count_first"], 1)
        self.assertEqual(ev["created"], False)
        self.assertIsNone(ev["created_token"])
        self.assertEqual(rec.create_calls, [])

    def test_zero_then_create_and_verify(self) -> None:
        pages_before = [_page([])]
        pages_after = [_page([{"name": "B48-VN", "type": "folder", "token": "tok-new"}])]
        rec = RecordingAdapter(pages_before, create_result={"token": "tok-new"}, list_pages_after_create=pages_after)
        adapter = Adapter(rec.list_children, rec.create_folder)
        ev = ensure_folder(adapter, "parent-2", "B48-VN")
        self.assertEqual(ev["resolution"], "created")
        self.assertEqual(ev["token"], "tok-new")
        self.assertEqual(ev["exact_match_count_first"], 0)
        self.assertEqual(ev["exact_match_count_second"], 0)
        self.assertEqual(ev["exact_match_count_after"], 1)
        self.assertEqual(ev["created"], True)
        self.assertEqual(ev["created_token"], "tok-new")
        self.assertEqual(rec.create_calls, ["B48-VN"])
        # Three listings total: before-first, before-second, after-create.
        self.assertEqual(len(rec.list_calls), 3)

    def test_first_zero_second_one_reuses_and_skips_create(self) -> None:
        # Simulate a concurrent actor: first listing empty, second listing has it.
        class ConcurrentAdapter(RecordingAdapter):
            def list_children(self, parent_token, page_token):
                self.list_calls.append(page_token)
                if len(self.list_calls) == 1:
                    return _page([])
                return _page([{"name": "Listing", "type": "folder", "token": "tok-race"}])

        rec = ConcurrentAdapter([], create_result={"token": "should-not-be-called"})
        adapter = Adapter(rec.list_children, rec.create_folder)
        ev = ensure_folder(adapter, "parent-3", "Listing")
        self.assertEqual(ev["resolution"], "reused")
        self.assertEqual(ev["token"], "tok-race")
        self.assertEqual(ev["exact_match_count_first"], 0)
        self.assertEqual(ev["exact_match_count_second"], 1)
        self.assertEqual(rec.create_calls, [])

    def test_multiple_matches_first_blocks(self) -> None:
        pages = [
            _page([
                {"name": "Listing", "type": "folder", "token": "tok-a"},
                {"name": "Listing", "type": "folder", "token": "tok-b"},
            ])
        ]
        rec = RecordingAdapter(pages, create_result={"token": "never"})
        adapter = Adapter(rec.list_children, rec.create_folder)
        with self.assertRaises(EnsureFolderError) as ctx:
            ensure_folder(adapter, "parent", "Listing")
        self.assertEqual(ctx.exception.code, "duplicate_folder")
        self.assertEqual(ctx.exception.details["stage"], "first")
        self.assertEqual(len(ctx.exception.details["candidates"]), 2)
        self.assertEqual(rec.create_calls, [])

    def test_multiple_matches_after_create_blocks(self) -> None:
        pages_before = [_page([])]
        pages_after = [_page([
            {"name": "B48-VN", "type": "folder", "token": "tok-1"},
            {"name": "B48-VN", "type": "folder", "token": "tok-2"},
        ])]
        rec = RecordingAdapter(pages_before, create_result={"token": "tok-1"}, list_pages_after_create=pages_after)
        adapter = Adapter(rec.list_children, rec.create_folder)
        with self.assertRaises(EnsureFolderError) as ctx:
            ensure_folder(adapter, "parent", "B48-VN")
        self.assertEqual(ctx.exception.code, "create_verification_failed")
        self.assertEqual(ctx.exception.details["stage"], "after")

    def test_create_token_mismatch_blocks(self) -> None:
        pages_before = [_page([])]
        pages_after = [_page([{"name": "B48-VN", "type": "folder", "token": "observed"}])]
        rec = RecordingAdapter(pages_before, create_result={"token": "returned"}, list_pages_after_create=pages_after)
        adapter = Adapter(rec.list_children, rec.create_folder)
        with self.assertRaises(EnsureFolderError) as ctx:
            ensure_folder(adapter, "parent", "B48-VN")
        self.assertEqual(ctx.exception.code, "create_token_mismatch")

    def test_pagination_finds_folder_across_pages(self) -> None:
        pages = [
            _page(
                [{"name": "Other", "type": "folder", "token": "tok-o"}],
                has_more=True,
                next_page_token="p2",
            ),
            _page(
                [{"name": "Listing", "type": "folder", "token": "tok-listing"}],
                this_page_token="p2",
            ),
        ]
        rec = RecordingAdapter(pages)
        adapter = Adapter(rec.list_children, rec.create_folder)
        ev = ensure_folder(adapter, "parent", "Listing")
        self.assertEqual(ev["resolution"], "reused")
        self.assertEqual(ev["token"], "tok-listing")
        self.assertEqual(ev["pages_scanned_first"], 2)

    def test_pagination_loop_blocks(self) -> None:
        class LoopingAdapter:
            def __init__(self):
                self.calls = 0

            def list_children(self, parent_token, page_token):
                self.calls += 1
                return _page([], has_more=True, next_page_token="loop")

            def create_folder(self, *a, **kw):
                raise AssertionError("no create")

        rec = LoopingAdapter()
        adapter = Adapter(rec.list_children, rec.create_folder)
        with self.assertRaises(EnsureFolderError) as ctx:
            ensure_folder(adapter, "parent", "X")
        self.assertEqual(ctx.exception.code, "pagination_loop")

    def test_malformed_response_blocks(self) -> None:
        class BadAdapter:
            def list_children(self, parent_token, page_token):
                return "not-a-dict"

            def create_folder(self, *a, **kw):
                raise AssertionError

        adapter = Adapter(BadAdapter().list_children, BadAdapter().create_folder)
        with self.assertRaises(EnsureFolderError) as ctx:
            ensure_folder(adapter, "parent", "X")
        self.assertEqual(ctx.exception.code, "malformed_response")

    def test_name_must_be_exact_case_and_whitespace(self) -> None:
        pages = [_page([
            {"name": "listing", "type": "folder", "token": "lower"},
            {"name": "Listing ", "type": "folder", "token": "trailing-space"},
            {"name": "Ｌisting", "type": "folder", "token": "fullwidth"},
        ])]
        # Zero exact matches -> create path expected. Provide a create result so
        # we can drop through and assert we didn't reuse any near-matches.
        pages_after = [_page([{"name": "Listing", "type": "folder", "token": "tok-new"}])]
        rec = RecordingAdapter(pages, create_result={"token": "tok-new"}, list_pages_after_create=pages_after)
        adapter = Adapter(rec.list_children, rec.create_folder)
        ev = ensure_folder(adapter, "parent", "Listing")
        self.assertEqual(ev["resolution"], "created")
        self.assertEqual(ev["token"], "tok-new")

    def test_evidence_has_resolved_at_with_timezone(self) -> None:
        pages = [_page([{"name": "Listing", "type": "folder", "token": "tok"}])]
        rec = RecordingAdapter(pages)
        adapter = Adapter(rec.list_children, rec.create_folder)
        ev = ensure_folder(adapter, "parent", "Listing")
        from datetime import datetime

        parsed = datetime.fromisoformat(ev["resolved_at"])
        self.assertIsNotNone(parsed.tzinfo)


# ---------------------------------------------------------------------------
# Concurrency test using multiprocessing 'spawn' to prove the file lock guards
# a real cross-process critical section.


def _worker(lock_dir: str, shared_state_path: str, result_path: str) -> None:
    """Runs in a spawned child process."""
    import fcntl
    import json
    import os
    import sys
    from pathlib import Path

    repo_root = Path(shared_state_path).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import scripts.ensure_feishu_folder as mod
    mod.LOCK_DIR = Path(lock_dir)

    state_path = Path(shared_state_path)

    def load_state():
        with state_path.open("r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                return json.loads(fh.read())
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def save_state(state):
        with state_path.open("r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.seek(0)
                fh.write(json.dumps(state))
                fh.truncate()
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    class SharedAdapter:
        def list_children(self, parent_token, page_token):
            state = load_state()
            files = state["files"]
            return {"files": files, "has_more": False, "next_page_token": None}

        def create_folder(self, parent_token, name):
            # Simulate a slow create to widen the race window.
            state = load_state()
            state["creates"] += 1
            token = f"tok-{state['creates']}"
            # Small sleep while lock is released between load/save is fine;
            # ensure_folder holds the ensure lock across this call.
            state["files"].append({"name": name, "type": "folder", "token": token})
            save_state(state)
            return {"token": token}

    adapter = mod.Adapter(SharedAdapter().list_children, SharedAdapter().create_folder)
    ev = mod.ensure_folder(adapter, "parent-shared", "Concurrent")
    with open(result_path, "w") as fh:
        fh.write(json.dumps(ev))


class ConcurrencyTests(unittest.TestCase):
    def test_two_processes_only_create_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / "locks"
            lock_dir.mkdir()
            state_path = Path(tmp) / "state.json"
            state_path.write_text(json.dumps({"files": [], "creates": 0}))
            result_a = Path(tmp) / "a.json"
            result_b = Path(tmp) / "b.json"
            ctx = mp.get_context("spawn")
            p_a = ctx.Process(target=_worker, args=(str(lock_dir), str(state_path), str(result_a)))
            p_b = ctx.Process(target=_worker, args=(str(lock_dir), str(state_path), str(result_b)))
            p_a.start()
            p_b.start()
            p_a.join(timeout=30)
            p_b.join(timeout=30)
            self.assertEqual(p_a.exitcode, 0)
            self.assertEqual(p_b.exitcode, 0)
            state = json.loads(state_path.read_text())
            self.assertEqual(state["creates"], 1, f"expected exactly one create, got {state['creates']}")
            self.assertEqual(len([f for f in state["files"] if f["name"] == "Concurrent"]), 1)
            ev_a = json.loads(result_a.read_text())
            ev_b = json.loads(result_b.read_text())
            # Exactly one process must have created, the other must have reused.
            resolutions = sorted([ev_a["resolution"], ev_b["resolution"]])
            self.assertEqual(resolutions, ["created", "reused"])
            self.assertEqual(ev_a["token"], ev_b["token"])


# ---------------------------------------------------------------------------
# SubprocessJSONAdapter contract


class SubprocessAdapterTests(unittest.TestCase):
    def test_parses_json_stdout_and_ignores_stderr(self) -> None:
        adapter = SubprocessJSONAdapter([sys.executable, "-c", """
import json, sys
op = sys.argv[1]
if op == 'list-children':
    print(json.dumps({'files': [{'name': 'Listing', 'type': 'folder', 'token': 'tok'}], 'has_more': False, 'next_page_token': None}))
elif op == 'create-folder':
    print(json.dumps({'token': 'tok'}))
sys.stderr.write('diagnostic\\n')
"""])
        resp = adapter.list_children("parent", None)
        self.assertEqual(resp["files"][0]["token"], "tok")
        resp = adapter.create_folder("parent", "Listing")
        self.assertEqual(resp["token"], "tok")

    def test_non_zero_exit_hard_fails(self) -> None:
        adapter = SubprocessJSONAdapter([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(1)"])
        with self.assertRaises(EnsureFolderError) as ctx:
            adapter.list_children("parent", None)
        self.assertEqual(ctx.exception.code, "adapter_error")

    def test_non_json_stdout_hard_fails(self) -> None:
        adapter = SubprocessJSONAdapter([sys.executable, "-c", "print('not-json')"])
        with self.assertRaises(EnsureFolderError) as ctx:
            adapter.list_children("parent", None)
        self.assertEqual(ctx.exception.code, "adapter_error")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
