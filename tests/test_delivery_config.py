import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "delivery_config.py"


class DeliveryConfigTest(unittest.TestCase):
    def run_cli(self, *args, check=True, env=None):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True, capture_output=True, env=env)
        if check and result.returncode:
            self.fail(result.stderr or result.stdout)
        return result

    def test_missing_and_corrupt_config_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            self.assertNotEqual(self.run_cli("status", "--config", path, check=False).returncode, 0)
            path.write_text("{broken", encoding="utf-8")
            self.assertNotEqual(self.run_cli("resolve", "--config", path, check=False).returncode, 0)

    def test_bootstrap_and_environment_path_default_to_docx(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            env = dict(os.environ, ECOMMERCE_LISTING_DELIVERY_CONFIG=str(path))
            result = self.run_cli("bootstrap", "--evidence-json", '{"docx_verified":true}', env=env)
            self.assertEqual(json.loads(result.stdout)["default_delivery_route"], "docx")
            self.assertEqual(json.loads(path.read_text())["schema_version"], 1)

    def test_bootstrap_rejects_secrets_recursively(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            result = self.run_cli("bootstrap", "--config", path, "--evidence-json", '{"nested":{"api_key":"nope"}}', check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(path.exists())

    def test_resolution_is_deterministic_and_override_is_one_shot(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            self.run_cli("bootstrap", "--config", path, "--delivery-route", "docx", "--evidence-json", '{}')
            first = json.loads(self.run_cli("resolve", "--config", path).stdout)
            second = json.loads(self.run_cli("resolve", "--config", path).stdout)
            self.assertEqual(first, second)
            self.assertEqual(first, {"delivery_route":"docx", "delivery_route_source":"skill_config", "delivery_config_schema_version":1, "delivery_override":None})
            override = json.loads(self.run_cli("resolve", "--config", path, "--override-route", "interactive_card", "--user-confirmation", "本次改用卡片").stdout)
            self.assertEqual(override["delivery_route_source"], "explicit_user_override")
            self.assertEqual(override["delivery_override"]["confirmation_text"], "本次改用卡片")
            self.assertEqual(json.loads(self.run_cli("resolve", "--config", path).stdout)["delivery_route"], "docx")

    def test_override_requires_user_confirmation_and_preview_is_never_route(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            self.run_cli("bootstrap", "--config", path, "--evidence-json", '{}')
            self.assertNotEqual(self.run_cli("resolve", "--config", path, "--override-route", "interactive_card", check=False).returncode, 0)
            self.assertNotEqual(self.run_cli("bootstrap", "--config", path, "--delivery-route", "preview_images", check=False).returncode, 0)

    def test_invalidate_blocks_resolve_and_record_success_sets_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            self.run_cli("bootstrap", "--config", path, "--evidence-json", '{}')
            self.run_cli("record-success", "--config", path)
            self.assertTrue(json.loads(path.read_text())["last_success_at"])
            self.run_cli("invalidate", "--config", path, "--reason", "permission revoked")
            self.assertNotEqual(self.run_cli("resolve", "--config", path, check=False).returncode, 0)

    def test_concurrent_bootstrap_never_corrupts_config(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "delivery.json"
            def bootstrap(_):
                return self.run_cli("bootstrap", "--config", path, "--delivery-route", "docx", "--evidence-json", '{}', check=False).returncode
            with ThreadPoolExecutor(max_workers=8) as pool:
                codes = list(pool.map(bootstrap, range(16)))
            self.assertEqual(codes, [0] * 16)
            self.assertEqual(json.loads(path.read_text())["default_delivery_route"], "docx")


if __name__ == "__main__":
    unittest.main()
