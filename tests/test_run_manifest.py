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

    def test_init_creates_nine_slots_and_required_sections(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--market", "VN", "--platform", "TikTok Shop")
            data = self.load(path)
            self.assertEqual([s["slot"] for s in data["images"]], list(range(1, 10)))
            for key in ["facts", "modules", "images", "qa", "tokens", "timings", "status"]:
                self.assertIn(key, data)

    def test_timing_records_stage_duration(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            self.run_cli("timing", path, "wave_0", "--seconds", "12.5")
            self.assertEqual(self.load(path)["timings"]["wave_0"]["seconds"], 12.5)

    def test_select_retry_returns_only_failed_slots(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            data["images"][1].update(status="failed", provider_error={"code": "timeout", "retryable": True})
            data["images"][5].update(status="failed", provider_error={"code": "safety_violation", "retryable": False})
            data["images"][7].update(status="success", file="Main001-08.png")
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("select-retry", path)
            self.assertEqual(json.loads(result.stdout)["slots"], [2])

    def test_validate_enforces_hard_reject_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            for slot in data["images"]:
                slot.update(status="success", file=f"Main001-{slot['slot']:02d}.png", qa_label="green")
            data["images"][0]["qa_label"] = "red"
            data["images"][0]["hard_reject_reason"] = "minor typo"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("validate", path, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hard_reject_reason", result.stderr)

    def test_validate_requires_complete_delivery_and_dual_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            for slot in data["images"]:
                n = slot["slot"]
                slot.update(status="success", file=f"Main001-{n:02d}.png", qa_label="green")
                data["tokens"][str(n)] = {"file_token": f"f{n}", "image_key": f"i{n}"}
            data["status"] = "ready"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.run_cli("validate", path, "--delivery")
            del data["tokens"]["9"]["image_key"]
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("validate", path, "--delivery", check=False)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
