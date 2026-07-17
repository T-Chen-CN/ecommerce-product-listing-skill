import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"
MUTATIONS = {"set-facts", "set-image-plan", "put-module", "update-slot", "set-token", "set-delivery", "timing", "finalize"}
sys.path.insert(0, str(ROOT / "scripts"))
import run_manifest


class ManifestV28PreservedContractsTest(unittest.TestCase):
    def cli(self, *args, check=True):
        args = list(map(str, args))
        if args and args[0] == "init" and "--delivery-route-file" not in args:
            manifest = Path(args[1]); route = manifest.parent / (manifest.name + ".route.json")
            route.write_text(json.dumps({"delivery_route":"interactive_card","delivery_route_source":"skill_config","delivery_config_schema_version":1,"delivery_override":None}))
            args += ["--delivery-route-file", str(route)]
        if args and args[0] in MUTATIONS and len(args) > 1 and Path(args[1]).exists() and not any(x in args for x in ("--revision", "--from-current")):
            d = json.loads(Path(args[1]).read_text())
            args += ["--manifest-id", d["manifest_id"], "--generation", str(d["generation"]), "--revision", str(d["revision"])]
        r = subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)
        if check and r.returncode:
            self.fail(r.stderr or r.stdout)
        return r

    def test_stale_revision_and_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            d = json.loads(p.read_text())
            self.cli("set-facts", p, "--json", '{"brand":"A"}')
            for args in (
                ("--manifest-id", d["manifest_id"], "--generation", d["generation"], "--revision", d["revision"]),
                ("--manifest-id", "wrong", "--generation", d["generation"], "--revision", d["revision"] + 1),
            ):
                flat = [str(x) for pair in zip(args[::2], args[1::2]) for x in pair]
                self.assertNotEqual(self.cli("set-facts", p, "--json", '{"brand":"B"}', *flat, check=False).returncode, 0)

    def test_localization_contract_and_prompt_isolation_remain(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p, "--task-scope", "full", "--requested-module", "title", "--target-language", "fr")
            bad = self.cli("put-module", p, "title", "--json", '{"source_text":"Titre","render_text":"Titre"}', check=False)
            self.assertIn("zh_reference", bad.stderr)
            leak = self.cli("update-slot", p, 1, "--json", '{"zh_reference":"中文卖点","prompt":"render 中文卖点"}', check=False)
            self.assertIn("prompt leaks", leak.stderr)

    def test_custom_plan_requires_explicit_count_and_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.assertNotEqual(self.cli("init", p, "--plan-mode", "custom", "--expected-count", 2, check=False).returncode, 0)
            self.cli("init", p, "--plan-mode", "custom", "--expected-count", 2, "--confirmed-by-user")
            self.assertEqual(len(json.loads(p.read_text())["images"]), 2)

    def test_content_scope_has_no_image_contract(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p, "--task-scope", "content", "--requested-module", "title")
            d = json.loads(p.read_text())
            self.assertEqual(d["expected_count"], 0)
            self.assertEqual(d["images"], [])

    def test_force_rebuilds_v4_as_v7_with_monotonic_identity(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            p.write_text(json.dumps({"schema_version": 4, "generation": 7, "revision": 12, "legacy": True}))
            self.cli("init", p, "--force")
            d = json.loads(p.read_text())
            self.assertEqual((d["schema_version"], d["generation"], d["revision"]), (8, 8, 13))

    def test_update_slot_rejects_identity_fields_and_removed_qa_fields(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            for payload in ('{"slot":2}', '{"qa_label":"green"}', '{"hard_reject_reason":"off_topic"}'):
                self.assertIn("unknown fields", self.cli("update-slot", p, 1, "--json", payload, check=False).stderr)

    def test_concurrent_from_current_writes_are_serialized_without_lost_updates(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            errors = []

            def worker(index):
                result = self.cli("put-module", p, f"m{index}", "--module-kind", "internal", "--json", json.dumps({"value": index}), "--from-current", check=False)
                if result.returncode:
                    errors.append(result.stderr)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]
            self.assertFalse(errors)
            data = json.loads(p.read_text())
            self.assertEqual(len(data["modules"]), 12)
            self.assertEqual(data["revision"], 12)

    def test_concurrent_requested_docx_modules_remain_valid(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            requested = [item for i in range(8) for item in ("--requested-module", f"docx{i}")]
            self.cli("init", p, "--task-scope", "content", "--market", "TH", *requested)
            errors = []

            def worker(index):
                payload = {"source_text": f"ข้อความ {index}", "zh_reference": f"中文 {index}", "render_text": f"ข้อความ {index}"}
                result = self.cli("put-module", p, f"docx{index}", "--module-kind", "docx_text", "--json", json.dumps(payload), "--from-current", check=False)
                if result.returncode:
                    errors.append(result.stderr)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]
            self.assertFalse(errors)
            self.assertEqual(len(json.loads(p.read_text())["requested_docx_modules"]), 8)
            self.cli("validate", p)

    def test_atomic_save_preserves_old_file_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            before = p.read_bytes()
            data = json.loads(p.read_text())
            data["status"] = "changed"
            with mock.patch("run_manifest.os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    run_manifest.atomic_save(p, data)
            self.assertEqual(p.read_bytes(), before)

    def test_updater_exception_and_replace_failure_preserve_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            before = p.read_bytes()
            with self.assertRaises(RuntimeError):
                run_manifest.mutate(p, lambda data: (_ for _ in ()).throw(RuntimeError("updater")))
            self.assertEqual(p.read_bytes(), before)
            with mock.patch("run_manifest.os.replace", side_effect=OSError("replace")):
                with self.assertRaises(OSError):
                    run_manifest.mutate(p, lambda data: data["facts"].update(notes="changed"))
            self.assertEqual(p.read_bytes(), before)

    def test_malformed_shapes_report_without_traceback(self):
        malformed = [None, {"images": [None]}, {"modules": []}, {"tokens": []}, {"delivery": []}, {"timings": []}]
        with tempfile.TemporaryDirectory() as td:
            for index, mutation in enumerate(malformed):
                p = Path(td) / f"bad-{index}.json"
                self.cli("init", p)
                if mutation is None:
                    p.write_text("[]")
                else:
                    data = json.loads(p.read_text())
                    data.update(mutation)
                    p.write_text(json.dumps(data))
                for command in (("validate", p), ("select-retry", p)):
                    result = self.cli(*command, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)

    def test_mutation_validates_candidate_before_save(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            before = p.read_bytes()
            result = self.cli("update-slot", p, 1, "--json", '{"provider_error":"bogus"}', check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(p.read_bytes(), before)

    def test_relative_success_image_path_resolves_from_manifest_directory(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            directory = Path(td)
            p = directory / "run.json"
            (directory / "relative.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.cli("init", p)
            self.cli("update-slot", p, 1, "--json", '{"status":"success","file":"relative.png","asset_filename":"Main001-01.png","image_batch":1}')
            result = subprocess.run([sys.executable, str(CLI), "validate", str(p)], cwd=other, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
