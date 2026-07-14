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
            image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture-image-data")
            slot.update(status="success", file=str(image), qa_label="green")

    def mark_delivery_ready(self, data, rejected=(), mode="docx"):
        rejected = set(rejected)
        deliverable = []
        for slot in data["images"]:
            n = slot["slot"]
            if n in rejected:
                slot.update(status="rejected", file=None, qa_label="red", hard_reject_reason="off_topic")
            else:
                deliverable.append(n)
                data["tokens"][str(n)] = {"image_key": f"img_v2_fixture_{n:02d}"}
                if mode == "docx":
                    data["tokens"][str(n)]["file_token"] = f"file_fixture_{n:02d}"
        data["delivery"] = {
            "deliverable_slots": deliverable,
            "rejected_slots": sorted(rejected),
            "docx": ({"token": "docx_fixture_token", "permalink": "https://docs.feishu.cn/docx/fixture"}
                     if mode == "docx" else {"token": None, "permalink": None}),
            "folder": ({"permalink": "https://acme.larksuite.com/drive/folder/fixture"}
                       if mode == "docx" else {"permalink": None}),
            "card": {"message_id": "om_fixture_message_123", "send_success": True},
        }
        data["qa"] = {"mode": "nine-image-single-round", "reviewed_at": "2026-07-14T09:30:00+00:00"}
        data["timings"] = {
            "wave_0": {"seconds": 1.25},
            "wave_1": {"seconds": 5.5},
            "wave_2": {"seconds": 8.0},
            "total": {"seconds": 9.0},
        }
        data["status"] = "ready"

    def test_init_defaults_to_docx_and_accepts_explicit_card_mode(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            default_path = directory / "default.json"
            card_path = directory / "card.json"
            self.run_cli("init", default_path)
            self.run_cli("init", card_path, "--delivery-mode", "card")
            self.assertEqual(self.load(default_path)["delivery_mode"], "docx")
            self.assertEqual(self.load(card_path)["delivery_mode"], "card")

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

    def test_timing_rejects_unknown_stage_and_non_finite_or_negative_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            for stage, seconds in [("other", "1"), ("wave_0", "-1"), ("wave_1", "nan"), ("total", "inf")]:
                with self.subTest(stage=stage, seconds=seconds):
                    result = self.run_cli("timing", path, stage, "--seconds", seconds, check=False)
                    self.assertNotEqual(result.returncode, 0)

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

    def test_validate_requires_supported_image_magic_bytes(self):
        signatures = {
            "png": b"\x89PNG\r\n\x1a\nrest",
            "jpeg": b"\xff\xd8\xff\xe0rest",
            "webp": b"RIFF\x04\x00\x00\x00WEBPrest",
            "gif": b"GIF89arest",
        }
        for extension, payload in signatures.items():
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                path = directory / "run.json"
                self.run_cli("init", path)
                data = self.load(path)
                image = directory / f"fixture.{extension}"
                image.write_bytes(payload)
                data["images"][0].update(status="success", file=str(image), qa_label="green")
                self.save(path, data)
                self.run_cli("validate", path)

        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            image = directory / "fake.png"
            image.write_bytes(b"not-an-image")
            data["images"][0].update(status="success", file=str(image), qa_label="green")
            self.save(path, data)
            result = self.run_cli("validate", path, check=False)
            self.assertIn("PNG/JPEG/WebP/GIF", result.stderr)
            data["images"][0]["file"] = str(directory)
            self.save(path, data)
            result = self.run_cli("validate", path, check=False)
            self.assertIn("readable regular file", result.stderr)

    def test_card_delivery_requires_only_image_keys_and_card_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            self.run_cli("init", path, "--delivery-mode", "card")
            data = self.load(path)
            self.make_success_files(directory, data)
            self.mark_delivery_ready(data, mode="card")
            self.save(path, data)
            self.run_cli("validate", path, "--delivery")

    def test_card_delivery_rejects_missing_image_key_and_forbidden_docx_evidence(self):
        mutations = [
            (lambda d: d["tokens"]["9"].pop("image_key"), "image_key required for card delivery"),
            (lambda d: d["tokens"]["9"].update(file_token="stale"), "must not retain docx or folder evidence"),
            (lambda d: d["delivery"]["docx"].update(token="stale"), "must not retain docx or folder evidence"),
            (lambda d: d["delivery"]["folder"].update(permalink="https://docs.feishu.cn/stale"), "must not retain docx or folder evidence"),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                path = directory / "run.json"
                self.run_cli("init", path, "--delivery-mode", "card")
                data = self.load(path)
                self.make_success_files(directory, data)
                self.mark_delivery_ready(data, mode="card")
                mutate(data)
                self.save(path, data)
                result = self.run_cli("validate", path, "--delivery", check=False)
                self.assertIn(expected, result.stderr)

    def test_delivery_rejects_pending_and_failed_slots(self):
        for status in ("pending", "failed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                path = directory / "run.json"
                self.run_cli("init", path)
                data = self.load(path)
                self.make_success_files(directory, data)
                self.mark_delivery_ready(data)
                data["images"][0].update(status=status, file=None, qa_label=None)
                self.save(path, data)
                result = self.run_cli("validate", path, "--delivery", check=False)
                self.assertIn(f"status {status} is not final", result.stderr)

    def test_delivery_requires_qa_audit_and_complete_valid_timings(self):
        mutations = [
            (lambda d: d["qa"].update(mode="per-image"), "qa.mode"),
            (lambda d: d["qa"].update(reviewed_at="not-a-time"), "qa.reviewed_at"),
            (lambda d: d["timings"].pop("wave_1"), "timings.wave_1"),
            (lambda d: d["timings"]["wave_2"].update(seconds=-1), "finite and >= 0"),
            (lambda d: d["timings"]["total"].update(seconds=float("nan")), "finite and >= 0"),
            (lambda d: d["timings"]["total"].update(seconds=4), "at least each wave"),
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
                self.assertIn(expected, result.stderr)

    def test_delivery_accepts_parallel_total_without_requiring_wave_sum(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            self.make_success_files(directory, data)
            self.mark_delivery_ready(data)
            self.assertLess(data["timings"]["total"]["seconds"], sum(data["timings"][s]["seconds"] for s in ("wave_0", "wave_1", "wave_2")))
            self.save(path, data)
            self.run_cli("validate", path, "--delivery")

    def test_delivery_validates_token_keys_values_urls_and_card_message(self):
        mutations = [
            (lambda d: d["tokens"].update(extra={"file_token": "file_unknown_slot"}), "unknown token slot"),
            (lambda d: d["tokens"]["9"].update(image_key="bad key"), "image_key must be"),
            (lambda d: d["tokens"]["9"].update(file_token="x"), "file_token must be"),
            (lambda d: d["delivery"]["docx"].update(token="bad token"), "docx token must be"),
            (lambda d: d["delivery"]["docx"].update(permalink="http://docs.feishu.cn/docx/x"), "docx permalink"),
            (lambda d: d["delivery"]["folder"].update(permalink="https://evilfeishu.cn/folder/x"), "folder permalink"),
            (lambda d: d["delivery"]["card"].update(message_id="x"), "message_id must be"),
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
                self.assertIn(expected, result.stderr)

    def test_card_rejects_file_token_anywhere_and_rejected_token_fields(self):
        mutations = [
            lambda d: d["tokens"].update({"3": {"file_token": "file_stale_rejected"}}),
            lambda d: d["tokens"].update({"3": {"image_key": "img_stale_rejected"}}),
        ]
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                path = directory / "run.json"
                self.run_cli("init", path, "--delivery-mode", "card")
                data = self.load(path)
                self.make_success_files(directory, data)
                self.mark_delivery_ready(data, rejected={3}, mode="card")
                mutate(data)
                self.save(path, data)
                result = self.run_cli("validate", path, "--delivery", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, "hard-rejected slot|file_token")

    def test_delivery_modes_accept_hard_reject_without_tokens_and_exclude_it(self):
        for mode in ("docx", "card"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                path = directory / "run.json"
                self.run_cli("init", path, "--delivery-mode", mode)
                data = self.load(path)
                self.make_success_files(directory, data)
                self.mark_delivery_ready(data, rejected={3}, mode=mode)
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
            (lambda d: d["tokens"]["9"].pop("image_key"), "image_key required for docx delivery"),
            (lambda d: d["tokens"]["9"].pop("file_token"), "file_token required for docx delivery"),
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
