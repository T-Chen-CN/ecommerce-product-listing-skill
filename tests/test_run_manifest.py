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


class ManifestCliTest(unittest.TestCase):
    def cli(self, *args, check=True):
        args = list(map(str, args))
        if args and args[0] in MUTATIONS and len(args) > 1 and Path(args[1]).exists() and not any(x in args for x in ("--revision", "--from-current")):
            data = json.loads(Path(args[1]).read_text())
            args += ["--manifest-id", data["manifest_id"], "--generation", str(data["generation"]), "--revision", str(data["revision"])]
        result = subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)
        if check and result.returncode:
            self.fail(result.stderr or result.stdout)
        return result

    def init(self, directory, mode="card", count=2):
        path = Path(directory) / "run.json"
        route = self.route_file(directory, "interactive_card" if mode in {"card", "interactive_card"} else "docx")
        args = ["init", path, "--plan-mode", "custom", "--expected-count", count, "--confirmed-by-user", "--delivery-config", route]
        if mode == "docx": args += ["--agent-name", "Agent", "--product-name", "Product", "--country-code", "US"]
        self.cli(*args)
        return path

    def ready(self, path, failed=(), mode="card"):
        data = json.loads(path.read_text())
        failed = set(failed)
        for slot in data["images"]:
            n = slot["slot"]
            if n in failed:
                slot.update(status="failed", file=None, provider_error={"code": "safety_violation", "message": "blocked"})
            else:
                image = path.parent / f"image-{n}.png"
                image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
                slot.update(status="success", file=str(image), provider_error=None, asset_filename=f"Main{n:03d}-01.png", image_batch=1)
                data["tokens"][str(n)] = {"image_key": f"img_fixture_{n}"}
                if mode == "docx":
                    data["tokens"][str(n)]["file_token"] = f"file_fixture_{n}"
        data["delivery"].update(
            deliverable_slots=[n for n in range(1, data["expected_count"] + 1) if n not in failed],
            failed_slots=sorted(failed),
            card={"message_id": "om_fixture_message", "send_success": True},
        )
        if mode == "docx":
            data["delivery"]["docx"] = {"token": "docx_fixture", "permalink": "https://docs.feishu.cn/docx/fixture"}
            data["delivery"]["folder"] = {"permalink": "https://acme.larksuite.com/drive/folder/fixture"}
        data["timings"] = {stage: {"seconds": value} for stage, value in (("wave_0", 1), ("wave_1", 2), ("wave_2", 3), ("total", 3))}
        data["status"] = "ready"
        path.write_text(json.dumps(data))
        return data

    def route_file(self, directory, route="interactive_card", source="skill_config", override=None):
        path = Path(directory) / f"route-{route}.json"
        path.write_text(json.dumps({"schema_version":1,"default_delivery_route":route,"bootstrap_evidence":{"evidence_version":1,"capability_version":"test","docx_capable":True,"interactive_card_capable":True,"verified_at":"2026-01-01T00:00:00+00:00","expires_at":"2099-01-01T00:00:00+00:00"},"configured_at":"2026-01-01T00:00:00+00:00","last_success_at":None,"invalidated_at":None,"invalidation_reason":None}))
        return path

    def test_schema_v8_requires_controlled_route_file_and_rejects_old_mode(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            missing = self.cli("init", path, check=False)
            self.assertNotEqual(missing.returncode, 0)
        self.assertIn("delivery-config", missing.stderr)
            old = self.cli("init", path, "--delivery-mode", "docx", check=False)
            self.assertNotEqual(old.returncode, 0)
            self.assertTrue("unrecognized arguments" in old.stderr or "delivery-config" in old.stderr)

    def test_route_sources_and_explicit_override_evidence_are_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            config = self.route_file(td)
            result = self.cli("init", Path(td) / "override.json", "--delivery-config", config,
                              "--delivery-route-override", "docx", check=False)
            self.assertIn("override-confirmation", result.stderr)

    def test_preview_images_cannot_be_a_formal_route(self):
        with tempfile.TemporaryDirectory() as td:
            route = self.route_file(td, route="preview_images")
            result = self.cli("init", Path(td) / "run.json", "--delivery-config", route, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("delivery_route", result.stderr)

    def test_init_uses_schema_v8_without_post_qa_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = json.loads(path.read_text())
            self.assertEqual(data["schema_version"], 8)
            self.assertEqual(data["delivery_route"], "interactive_card")
            self.assertEqual(data["delivery_route_source"], "skill_config")
            self.assertNotIn("qa", data)
            self.assertEqual(set(data["delivery"]) & {"deliverable_slots", "failed_slots"}, {"deliverable_slots", "failed_slots"})
            self.assertNotIn("rejected_slots", data["delivery"])
            self.assertTrue(all("qa_label" not in x and "hard_reject_reason" not in x for x in data["images"]))
            expected_slot_fields = {"slot", "purpose", "prompt", "status", "file", "provider_error", "asset_filename", "image_batch"}
            self.assertTrue(all(set(slot) == expected_slot_fields for slot in data["images"]))

    def test_success_and_failed_are_jointly_final(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            self.ready(path, failed={2})
            result = self.cli("validate", path, "--delivery", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_success_requires_real_image_and_delivery_token(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = self.ready(path)
            Path(data["images"][0]["file"]).write_text("not image")
            data["tokens"].pop("2")
            path.write_text(json.dumps(data))
            result = self.cli("validate", path, "--delivery", check=False)
            self.assertIn("magic bytes", result.stderr)
            self.assertIn("image_key required", result.stderr)

    def test_failed_requires_error_and_forbids_any_token_entry(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = self.ready(path, failed={2})
            data["images"][1]["provider_error"] = None
            data["tokens"]["2"] = {}
            path.write_text(json.dumps(data))
            result = self.cli("validate", path, "--delivery", check=False)
            self.assertIn("status failed requires provider_error", result.stderr)
            self.assertIn("failed slot must not have token", result.stderr)

    def test_failed_provider_error_requires_typed_non_empty_core_fields(self):
        invalid_cases = [
            ({}, "provider_error.code must be non-empty string"),
            ({"code": "timeout", "message": ""}, "provider_error.message must be non-empty string"),
            ({"code": " ", "message": "timed out"}, "provider_error.code must be non-empty string"),
            ({"code": 1, "message": "timed out"}, "provider_error.code must be non-empty string"),
            ({"code": "timeout", "message": []}, "provider_error.message must be non-empty string"),
            ({"code": "timeout", "message": "timed out", "retryable": 1}, "provider_error.retryable must be bool"),
            ({"code": "timeout", "message": "timed out", "provider": 1}, "provider_error.provider must be string"),
            ({"code": "timeout", "message": "timed out", "request_id": False}, "provider_error.request_id must be string"),
            ({"code": "timeout", "message": "timed out", "status": "500"}, "provider_error.status must be HTTP status integer"),
            ({"code": "timeout", "message": "timed out", "status": 99}, "provider_error.status must be HTTP status integer"),
        ]
        for provider_error, expected in invalid_cases:
            with self.subTest(provider_error=provider_error), tempfile.TemporaryDirectory() as td:
                path = self.init(td)
                data = json.loads(path.read_text())
                data["images"][0].update(status="failed", provider_error=provider_error)
                path.write_text(json.dumps(data))
                result = self.cli("validate", path, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)

    def test_failed_provider_error_accepts_supported_optional_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = json.loads(path.read_text())
            data["images"][0].update(
                status="failed",
                provider_error={
                    "code": "timeout",
                    "message": "upstream timed out",
                    "retryable": True,
                    "provider": "openai",
                    "request_id": "req_123",
                    "status": 504,
                },
            )
            path.write_text(json.dumps(data))
            result = self.cli("validate", path, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_docx_and_interactive_card_delivery_evidence_are_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td, mode="docx", count=1)
            data = self.ready(path, mode="docx")
            data["delivery"]["card"] = {"message_id": None, "send_success": False}
            path.write_text(json.dumps(data))
            result = self.cli("validate", path, "--delivery", check=False)
            self.assertNotIn("card send_success", result.stderr)

    def test_card_forbids_file_tokens_and_docx_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = self.ready(path)
            data["tokens"]["1"]["file_token"] = "file_stale"
            path.write_text(json.dumps(data))
            self.assertIn("interactive_card delivery must not", self.cli("validate", path, "--delivery", check=False).stderr)

    def test_timing_and_retry_code_validation_remain(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            for seconds in ("-1", "nan", "inf"):
                self.assertNotEqual(self.cli("timing", path, "wave_0", "--seconds", seconds, check=False).returncode, 0)
            data = json.loads(path.read_text())
            data["images"][0].update(status="failed", provider_error={"code": "timeout", "message": "timed out", "retryable": False})
            data["images"][1].update(status="failed", provider_error={"code": "safety_violation", "message": "blocked", "retryable": True})
            path.write_text(json.dumps(data))
            self.assertEqual(json.loads(self.cli("select-retry", path).stdout)["slots"], [1])

    def test_closed_schema_rejects_removed_fields_and_set_qa_command(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = json.loads(path.read_text())
            data["qa"] = {}
            data["images"][0]["qa_label"] = "green"
            data["images"][0]["replaces_slot"] = None
            data["images"][0]["attempt"] = 1
            data["images"][0]["predecessor_slot"] = None
            data["delivery"]["rejected_slots"] = []
            path.write_text(json.dumps(data))
            result = self.cli("validate", path, check=False)
            self.assertIn("unknown fields", result.stderr)
            for command in ("set-qa", "add-replacement", "add-replacement-slot", "set-short-delivery-approval"):
                with self.subTest(command=command):
                    result = self.cli(command, path, "--json", "{}", check=False)
                    self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
