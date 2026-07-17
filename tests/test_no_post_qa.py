import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"
OPERATIONAL_DOCS = ["SKILL.md", "QUALITY_GATE.md", "OUTPUT_TEMPLATE.md", "README.md"]


class NoPostQaContractTest(unittest.TestCase):
    def run_cli(self, *args, check=True):
        result = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            text=True,
            capture_output=True,
        )
        if check and result.returncode:
            self.fail(result.stderr or result.stdout)
        return result

    def test_operational_docs_remove_post_qa_and_define_direct_delivery(self):
        joined = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in OPERATIONAL_DOCS)
        for forbidden in ("Post-QA", "后置 QA", "🟢", "🟡", "🔴", "single-round", "reviewed_at", "hard reject", "soft pass"):
            self.assertNotIn(forbidden, joined, forbidden)
        for required in ("Pre-QA", "生成成功", "直接交付", "生成失败", "按序号"):
            self.assertIn(required, joined, required)

    def test_manifest_has_no_qa_contract_or_qa_slot_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            route = Path(td) / "route.json"
            route.write_text(json.dumps({"schema_version":1,"default_delivery_route":"interactive_card","bootstrap_evidence":{"evidence_version":1,"capability_version":"test","docx_capable":True,"interactive_card_capable":True,"verified_at":"2026-01-01T00:00:00+00:00","expires_at":"2099-01-01T00:00:00+00:00"},"configured_at":"2026-01-01T00:00:00+00:00","last_success_at":None,"invalidated_at":None,"invalidation_reason":None}))
            self.run_cli("init", path, "--delivery-config", route)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("qa", data)
            for slot in data["images"]:
                self.assertNotIn("qa_label", slot)
                self.assertNotIn("hard_reject_reason", slot)

    def test_delivery_accepts_generation_failure_without_review_or_approval(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            path = directory / "run.json"
            route = Path(td) / "route.json"
            route.write_text(json.dumps({"schema_version":1,"default_delivery_route":"interactive_card","bootstrap_evidence":{"evidence_version":1,"capability_version":"test","docx_capable":True,"interactive_card_capable":True,"verified_at":"2026-01-01T00:00:00+00:00","expires_at":"2099-01-01T00:00:00+00:00"},"configured_at":"2026-01-01T00:00:00+00:00","last_success_at":None,"invalidated_at":None,"invalidation_reason":None}))
            self.run_cli("init", path, "--delivery-config", route)
            data = json.loads(path.read_text(encoding="utf-8"))
            deliverable = []
            for slot in data["images"]:
                if slot["slot"] == 3:
                    slot.update(status="failed", file=None, provider_error={"code": "safety_violation", "message": "blocked"})
                    continue
                image = directory / f"image-{slot['slot']}.png"
                image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
                slot.update(status="success", file=str(image))
                deliverable.append(slot["slot"])
                data["tokens"][str(slot["slot"])] = {"image_key": f"img_fixture_{slot['slot']:02d}"}
            data["delivery"].update(
                deliverable_slots=deliverable,
                failed_slots=[3],
                card={"message_id": "om_fixture_message", "send_success": True},
            )
            data["timings"] = {
                stage: {"seconds": seconds}
                for stage, seconds in (("wave_0", 1), ("wave_1", 2), ("wave_2", 3), ("total", 3))
            }
            data["status"] = "ready"
            path.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("validate", path, "--delivery", check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_set_qa_command_is_removed(self):
        result = self.run_cli("set-qa", "missing.json", "--json", "{}", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
