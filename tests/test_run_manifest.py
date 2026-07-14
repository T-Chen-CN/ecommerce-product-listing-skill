import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"


class ManifestCliTest(unittest.TestCase):
    def run_cli(self, *args, check=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True, capture_output=True)
        if check and result.returncode:
            self.fail(result.stderr or result.stdout)
        return result

    def load(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def save(self, path, data):
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    def make_success_files(self, directory, data):
        for slot in data["images"]:
            image = directory / f"Main001-{slot['slot']:02d}.png"
            image.write_bytes(b"real temporary image fixture")
            slot.update(status="success", file=str(image), qa_label="green")

    def mark_delivery_ready(self, data, rejected=()):
        rejected = set(rejected)
        deliverable = []
        for slot in data["images"]:
            n = slot["slot"]
            if n in rejected:
                slot.update(status="rejected", file=None, qa_label="red", hard_reject_reason="off_topic")
            else:
                deliverable.append(n)
                data["tokens"][str(n)] = {"file_token": f"f{n}", "image_key": f"i{n}"}
        data["delivery"] = {
            "deliverable_slots": deliverable,
            "rejected_slots": sorted(rejected),
            "docx": {"token": "doc-token", "permalink": "https://example.test/docx"},
            "folder": {"permalink": "https://example.test/folder"},
            "card": {"message_id": "om_123", "send_success": True},
        }
        data["status"] = "ready"

    def test_init_creates_nine_slots_and_delivery_evidence_shape(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--market", "VN", "--platform", "TikTok Shop")
            data = self.load(path)
            self.assertEqual([s["slot"] for s in data["images"]], list(range(1, 10)))
            for key in ["facts", "modules", "images", "qa", "tokens", "delivery", "timings", "status"]:
                self.assertIn(key, data)
            self.assertEqual(data["delivery"]["card"]["send_success"], False)

    def test_timing_records_stage_duration(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            self.run_cli("timing", path, "wave_0", "--seconds", "12.5")
            self.assertEqual(self.load(path)["timings"]["wave_0"]["seconds"], 12.5)

    def test_select_retry_uses_code_as_authority_under_boolean_conflicts(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            cases = [
                (1, {"code": "timeout", "retryable": False}),
                (2, {"code": "safety_violation", "retryable": True}),
                (3, {"retryable": True}),
                (4, {"code": "future_unknown", "retryable": True}),
                (5, {"code": "rate_limit"}),
            ]
            for index, error in cases:
                data["images"][index - 1].update(status="failed", provider_error=error)
            data["images"][5].update(status="success", provider_error={"code": "timeout"})
            self.save(path, data)
            result = self.run_cli("select-retry", path)
            self.assertEqual(json.loads(result.stdout)["slots"], [1, 5])

    def test_validate_enforces_label_status_reason_consistency(self):
        invalid_cases = [
            ("blue", "success", None, "qa_label"),
            ("red", "success", "off_topic", "requires status rejected"),
            ("yellow", "rejected", None, "status rejected requires"),
            ("green", "success", "off_topic", "hard_reject_reason requires"),
        ]
        for label, status, reason, expected in invalid_cases:
            with self.subTest(label=label, status=status, reason=reason), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "run.json"
                self.run_cli("init", path)
                data = self.load(path)
                data["images"][0].update(qa_label=label, status=status, hard_reject_reason=reason)
                self.save(path, data)
                result = self.run_cli("validate", path, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)

    def test_validate_requires_existing_readable_regular_success_file(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            data["images"][0].update(status="success", file=str(directory / "missing.png"), qa_label="green")
            self.save(path, data)
            result = self.run_cli("validate", path, check=False)
            self.assertIn("readable regular file", result.stderr)
            data["images"][0]["file"] = str(directory)
            self.save(path, data)
            result = self.run_cli("validate", path, check=False)
            self.assertIn("readable regular file", result.stderr)

    def test_delivery_accepts_hard_reject_without_tokens_and_excludes_it(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            self.make_success_files(directory, data)
            self.mark_delivery_ready(data, rejected={3})
            self.save(path, data)
            self.run_cli("validate", path, "--delivery")
            self.assertNotIn("3", data["tokens"])
            self.assertNotIn(3, data["delivery"]["deliverable_slots"])

    def test_delivery_rejects_red_slot_in_deliverable_set(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            self.make_success_files(directory, data)
            self.mark_delivery_ready(data, rejected={3})
            data["delivery"]["deliverable_slots"].append(3)
            self.save(path, data)
            result = self.run_cli("validate", path, "--delivery", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("deliverable_slots", result.stderr)

    def test_delivery_requires_dual_tokens_docx_folder_and_card_evidence(self):
        mutations = [
            (lambda d: d["tokens"]["9"].pop("image_key"), "both file_token and image_key"),
            (lambda d: d["delivery"]["docx"].pop("token"), "docx token and permalink"),
            (lambda d: d["delivery"]["docx"].pop("permalink"), "docx token and permalink"),
            (lambda d: d["delivery"]["folder"].pop("permalink"), "folder permalink"),
            (lambda d: d["delivery"]["card"].pop("message_id"), "card send_success true and message_id"),
            (lambda d: d["delivery"]["card"].update(send_success=False), "card send_success true and message_id"),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                path = directory / "run.json"
                self.run_cli("init", path)
                data = self.load(path)
                self.make_success_files(directory, data)
                self.mark_delivery_ready(data)
                mutate(data)
                self.save(path, data)
                result = self.run_cli("validate", path, "--delivery", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
