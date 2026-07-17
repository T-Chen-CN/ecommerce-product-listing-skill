import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"
MUTATIONS = {"set-facts", "set-image-plan", "put-module", "update-slot", "set-token", "set-delivery", "timing", "finalize"}


class FinalReviewSecurityTest(unittest.TestCase):
    def cli(self, *args, check=True):
        args = list(map(str, args))
        if args and args[0] == "init" and "--delivery-mode" not in args:
            args += ["--delivery-mode", "card"]
        if args and args[0] in MUTATIONS and len(args) > 1 and Path(args[1]).exists() and not any(x in args for x in ("--revision", "--from-current")):
            d = json.loads(Path(args[1]).read_text())
            args += ["--manifest-id", d["manifest_id"], "--generation", str(d["generation"]), "--revision", str(d["revision"])]
        r = subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)
        if check and r.returncode:
            self.fail(r.stderr or r.stdout)
        return r

    def test_non_chinese_han_prompt_rejected_but_japanese_kanji_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            fr = Path(td) / "fr.json"
            ja = Path(td) / "ja.json"
            self.cli("init", fr, "--target-language", "fr")
            self.cli("init", ja, "--target-language", "ja")
            self.assertIn("Han text forbidden", self.cli("update-slot", fr, 1, "--json", '{"prompt":"高品質"}', check=False).stderr)
            self.cli("update-slot", ja, 1, "--json", '{"prompt":"高品質"}')

    def test_file_containment_rejects_parent_absolute_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "run"
            root.mkdir()
            p = root / "run.json"
            self.cli("init", p)
            outside = Path(td) / "outside.png"
            outside.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            link = root / "link.png"
            link.symlink_to(outside)
            for value in (str(outside), "../outside.png", str(link)):
                d = json.loads(p.read_text())
                d["images"][0].update(status="success", file=value)
                p.write_text(json.dumps(d))
                self.assertIn("contained in run_root", self.cli("validate", p, check=False).stderr)

    def test_atomic_save_preserves_existing_mode(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            os.chmod(p, 0o640)
            self.cli("set-facts", p, "--json", '{"brand":"Fixture"}')
            self.assertEqual(p.stat().st_mode & 0o777, 0o640)

    def test_nested_closed_schema_and_provider_error_shape_remain(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            d = json.loads(p.read_text())
            d["images"][0]["provider_error"] = {"code": "timeout", "evil": 1}
            d["delivery"]["card"]["evil"] = True
            p.write_text(json.dumps(d))
            r = self.cli("validate", p, check=False)
            self.assertIn("provider_error", r.stderr)
            self.assertIn("delivery.card", r.stderr)

    def test_bool_slot_and_unknown_token_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            self.assertNotEqual(self.cli("set-token", p, "true", "--json", '{"image_key":"img_fixture"}', check=False).returncode, 0)
            d = json.loads(p.read_text())
            d["tokens"]["999"] = {"image_key": "img_fixture"}
            p.write_text(json.dumps(d))
            self.assertIn("unknown token slot", self.cli("validate", p, "--delivery", check=False).stderr)

    def test_finalize_does_not_accept_replacement_or_short_delivery_commands(self):
        for command in ("add-replacement-slot", "set-short-delivery-approval", "set-qa"):
            result = self.cli(command, "missing.json", check=False)
            self.assertIn("invalid choice", result.stderr)

    def test_from_current_refuses_same_field_blind_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p)
            self.cli("put-module", p, "memo", "--module-kind", "internal", "--json", '{"v":1}', "--from-current")
            result = self.cli("put-module", p, "memo", "--module-kind", "internal", "--json", '{"v":2}', "--from-current", check=False)
            self.assertIn("already exists", result.stderr)
            self.cli("timing", p, "wave_0", "--seconds", 1, "--from-current")
            result = self.cli("timing", p, "wave_0", "--seconds", 2, "--from-current", check=False)
            self.assertIn("already exists", result.stderr)
            data = json.loads(p.read_text())
            self.assertEqual(data["modules"]["memo"], {"v": 1})
            self.assertEqual(data["timings"]["wave_0"]["seconds"], 1)

    def test_localization_approval_shapes_fields_and_timestamps_are_deeply_validated(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p, "--task-scope", "content", "--target-language", "fr", "--monolingual", "--monolingual-confirmation", "French only", "--requested-module", "title")
            base = json.loads(p.read_text())
            cases = []
            for field in ("localization_policy", "target_only_approval"):
                data = json.loads(json.dumps(base))
                if field == "localization_policy":
                    data[field]["override"] = "bad"
                else:
                    data[field] = "bad"
                cases.append(data)
            for field, value in (("approved_by", 1), ("confirmation_text", []), ("recorded_at", "yesterday")):
                data = json.loads(json.dumps(base))
                data["localization_policy"]["override"][field] = value
                cases.append(data)
                data = json.loads(json.dumps(base))
                data["target_only_approval"][field] = value
                cases.append(data)
            for index, data in enumerate(cases):
                q = Path(td) / f"policy-{index}.json"
                q.write_text(json.dumps(data))
                self.assertNotEqual(self.cli("validate", q, check=False).returncode, 0)

    def test_requested_docx_modules_must_be_predeclared(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            self.cli("init", p, "--task-scope", "content", "--requested-module", "title", "--requested-module", "bullets")
            self.cli("put-module", p, "title", "--json", '{"source_text":"Titre","zh_reference":"标题","render_text":"Titre"}')
            self.assertEqual(json.loads(p.read_text())["requested_docx_modules"], ["title", "bullets"])
            self.assertNotEqual(self.cli("validate", p, check=False).returncode, 0)
            result = self.cli("put-module", p, "undeclared", "--json", '{"source_text":"X","zh_reference":"中文","render_text":"X"}', check=False)
            self.assertIn("predeclared", result.stderr)

    def test_prompt_leakage_detects_sibling_and_nested_fragments(self):
        payloads = (
            '[{"slot":1,"zh_reference":"轻便防水夹克","render_text":"veste","prompt":"photo 轻便防水 premium"}]',
            '[{"slot":1,"zh_reference":"轻便防水夹克","render_text":"veste","prompt":{"nested":{"prompt":"studio 防水夹克"}}}]',
        )
        with tempfile.TemporaryDirectory() as td:
            for index, payload in enumerate(payloads):
                p = Path(td) / f"run-{index}.json"
                self.cli("init", p)
                self.assertIn("prompt", self.cli("set-image-plan", p, "--json", payload, check=False).stderr)

    def test_force_rebuilds_old_schema_as_v6_and_rejects_bad_identity_types(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "run.json"
            p.write_text(json.dumps({"schema_version": 4, "generation": 7, "revision": 12, "legacy": "anything"}))
            self.cli("init", p, "--force")
            data = json.loads(p.read_text())
            self.assertEqual((data["schema_version"], data["generation"], data["revision"]), (6, 8, 13))
            for field, value in (("generation", True), ("revision", "12"), ("generation", 0), ("revision", -1)):
                p.write_text(json.dumps({"schema_version": 4, "generation": 7, "revision": 12, field: value}))
                self.assertNotEqual(self.cli("init", p, "--force", check=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
