import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"
sys.path.insert(0, str(ROOT / "scripts"))
import run_manifest


class DeliveryDirectoryContractTest(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True, capture_output=True)

    def init(self, td, mode="docx", scope="image", name="咖啡 机/Pro", country="jp"):
        path = Path(td) / "run.json"
        args = ["init", path, "--delivery-mode", mode, "--task-scope", scope]
        if mode == "docx":
            args += ["--agent-name", "Agent A", "--product-name", name, "--country-code", country]
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def ready_docx(self, td):
        path = self.init(td)
        data = json.loads(path.read_text())
        slug = data["product_slug"]
        chain = [
            {"name": "Agent A", "token": "fld_agent", "type": "folder", "parent_token": "root"},
            {"name": "电商需求", "token": "fld_ecom", "type": "folder", "parent_token": "fld_agent"},
            {"name": "Listing", "token": "fld_listing", "type": "folder", "parent_token": "fld_ecom"},
            {"name": slug, "token": "fld_product", "type": "folder", "parent_token": "fld_listing"},
        ]
        for image in data["images"]:
            n = image["slot"]
            image_file = Path(td) / f"Main{n:03d}-01.png"
            image_file.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            image.update(status="success", file=str(image_file), provider_error=None,
                         asset_filename=image_file.name, image_batch=1)
            data["tokens"][str(n)] = {"image_key": f"image_key_{n}", "file_token": f"file_token_{n}"}
        data["delivery"].update(
            deliverable_slots=list(range(1, 10)), failed_slots=[],
            directory_chain=chain, product_folder_token="fld_product",
            docx={"token": "docx_token", "permalink": "https://docs.feishu.cn/docx/docx_token",
                  "docx_filename": f"20260717-{slug}-001.docx", "docx_batch": 1},
            folder={"token": "fld_product", "permalink": "https://docs.feishu.cn/drive/folder/fld_product"},
            card={"message_id": "message_token", "send_success": True},
        )
        data["timings"] = {stage: {"seconds": 1} for stage in ("wave_0", "wave_1", "wave_2", "total")}
        data["status"] = "ready"
        path.write_text(json.dumps(data, ensure_ascii=False))
        return path, data

    def validate_delivery(self, path):
        return self.cli("validate", path, "--delivery")

    def test_init_schema_v6_records_docx_identity_and_empty_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td)
            data = json.loads(path.read_text())
            self.assertEqual(data["schema_version"], 6)
            self.assertEqual(data["agent_name"], "Agent A")
            self.assertEqual(data["product_slug"], "咖啡-机Pro-JP")
            self.assertEqual(data["market_country_code"], "JP")
            self.assertEqual(data["drive_path_segments"], ["Agent A", "电商需求", "Listing", "咖啡-机Pro-JP"])
            self.assertEqual(data["delivery"]["directory_chain"], [])
            self.assertIsNone(data["delivery"]["product_folder_token"])
            self.assertIn("docx_filename", data["delivery"]["docx"])
            self.assertIn("docx_batch", data["delivery"]["docx"])

    def test_docx_init_requires_explicit_identity_but_card_does_not_fabricate_it(self):
        with tempfile.TemporaryDirectory() as td:
            missing = self.cli("init", Path(td) / "bad.json", "--delivery-mode", "docx")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("--agent-name", missing.stderr)
            card = self.init(td, mode="card")
            data = json.loads(card.read_text())
            for field in ("agent_name", "product_slug", "market_country_code", "drive_path_segments"):
                self.assertNotIn(field, data)
            self.assertNotIn("directory_chain", data["delivery"])
            self.assertNotIn("product_folder_token", data["delivery"])
            self.assertNotIn("docx_filename", data["delivery"]["docx"])
            self.assertNotIn("docx_batch", data["delivery"]["docx"])

    def test_slug_function_and_cli_cover_boundaries_without_semantic_heuristics(self):
        cases = [
            ("  A  B / C\\:*?\"<>| -- ", "us", "A-B-C-US"),
            ("Revision red 中文", "gb", "Revision-red-中文-GB"),
            ("foo---bar", "DE", "foo-bar-DE"),
        ]
        for product, country, expected in cases:
            with self.subTest(product=product):
                self.assertEqual(run_manifest.product_slug(product, country), expected)
                result = self.cli("slug", "--product-name", product, "--country-code", country)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
        for product, country in ((" /\\:*?\"<>| ", "US"), ("valid", "USA"), ("valid", "1A")):
            with self.subTest(product=product, country=country):
                with self.assertRaises(ValueError):
                    run_manifest.product_slug(product, country)

    def test_valid_docx_directory_filename_and_assets_pass(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = self.ready_docx(td)
            result = self.validate_delivery(path)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_directory_path_wrong_layer_order_or_chain_evidence_fails(self):
        mutations = {
            "path": lambda d: d["drive_path_segments"].__setitem__(1, "错误"),
            "order": lambda d: d["delivery"]["directory_chain"].__setitem__(1, d["delivery"]["directory_chain"][2]),
            "missing": lambda d: d["delivery"].__setitem__("directory_chain", []),
            "empty_token": lambda d: d["delivery"]["directory_chain"][1].__setitem__("token", ""),
            "placeholder": lambda d: d["delivery"]["directory_chain"][1].__setitem__("token", "TODO"),
            "duplicate": lambda d: d["delivery"]["directory_chain"][2].__setitem__("token", "fld_ecom"),
            "wrong_parent": lambda d: d["delivery"]["directory_chain"][2].__setitem__("parent_token", "fld_agent"),
            "self_parent": lambda d: d["delivery"]["directory_chain"][2].__setitem__("parent_token", "fld_listing"),
            "wrong_final": lambda d: d["delivery"].__setitem__("product_folder_token", "other_token"),
            "wrong_type": lambda d: d["delivery"]["directory_chain"][0].__setitem__("type", "docx"),
            "root_parent": lambda d: d["delivery"]["directory_chain"][0].__setitem__("parent_token", None),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                path, data = self.ready_docx(td)
                mutate(data)
                path.write_text(json.dumps(data, ensure_ascii=False))
                self.assertNotEqual(self.validate_delivery(path).returncode, 0)

    def test_valid_permalinks_without_chain_still_fail(self):
        with tempfile.TemporaryDirectory() as td:
            path, data = self.ready_docx(td)
            data["delivery"]["directory_chain"] = []
            path.write_text(json.dumps(data, ensure_ascii=False))
            self.assertIn("directory_chain", self.validate_delivery(path).stderr)

    def test_docx_filename_date_slug_and_batch_must_match(self):
        bad_names = [
            ("20260230-咖啡-机Pro-JP-001.docx", 1),
            ("20260717-other-JP-001.docx", 1),
            ("20260717-咖啡-机Pro-JP-002.docx", 1),
            ("20260717-咖啡-机Pro-JP-000.docx", 0),
        ]
        for filename, batch in bad_names:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                path, data = self.ready_docx(td)
                data["delivery"]["docx"].update(docx_filename=filename, docx_batch=batch)
                path.write_text(json.dumps(data, ensure_ascii=False))
                self.assertNotEqual(self.validate_delivery(path).returncode, 0)

    def test_asset_filename_slot_and_batch_must_match_current_asset(self):
        bad = [("Main002-01.png", 1), ("SKU001-02.png", 1), ("Main001-00.png", 0), ("replacement001-01.png", 1)]
        for filename, batch in bad:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                path, data = self.ready_docx(td)
                data["images"][0].update(asset_filename=filename, image_batch=batch)
                path.write_text(json.dumps(data, ensure_ascii=False))
                self.assertNotEqual(self.validate_delivery(path).returncode, 0)

    def test_asset_filename_must_equal_real_path_name_and_use_supported_extension(self):
        for filename in ("Main001-01.jpg", "Main001-01.svg"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as td:
                path, data = self.ready_docx(td)
                data["images"][0]["asset_filename"] = filename
                path.write_text(json.dumps(data, ensure_ascii=False))
                self.assertNotEqual(self.validate_delivery(path).returncode, 0)

    def test_country_code_rejects_reserved_placeholders(self):
        for country in ("ZZ", "AA"):
            with self.subTest(country=country):
                with self.assertRaises(ValueError):
                    run_manifest.product_slug("valid", country)

    def test_slug_rejects_control_characters_and_dot_bodies(self):
        for product in ("bad\nname", ".", ".."):
            with self.subTest(product=repr(product)):
                with self.assertRaises(ValueError):
                    run_manifest.product_slug(product, "US")

    def test_docx_date_must_equal_created_at_utc_date_and_created_at_needs_timezone(self):
        with tempfile.TemporaryDirectory() as td:
            path, data = self.ready_docx(td)
            data["delivery"]["docx"]["docx_filename"] = f"20260716-{data['product_slug']}-001.docx"
            path.write_text(json.dumps(data, ensure_ascii=False))
            self.assertNotEqual(self.validate_delivery(path).returncode, 0)
            data["created_at"] = "2026-07-17T12:00:00"
            path.write_text(json.dumps(data, ensure_ascii=False))
            self.assertIn("created_at", self.validate_delivery(path).stderr)

    def test_folder_and_docx_permalink_tokens_must_match_declared_tokens(self):
        mutations = (
            lambda d: d["delivery"]["folder"].__setitem__("token", "other_folder"),
            lambda d: d["delivery"]["folder"].__setitem__("permalink", "https://docs.feishu.cn/drive/folder/other_folder"),
            lambda d: d["delivery"]["docx"].__setitem__("permalink", "https://docs.feishu.cn/docx/other_docx"),
        )
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as td:
                path, data = self.ready_docx(td)
                mutate(data)
                path.write_text(json.dumps(data, ensure_ascii=False))
                self.assertNotEqual(self.validate_delivery(path).returncode, 0)

    def test_content_scope_still_requires_strict_docx_directory_contract(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td, scope="content")
            data = json.loads(path.read_text())
            data["requested_docx_modules"] = ["title"]
            data["module_contracts"] = {"title": "docx_text"}
            data["modules"] = {"title": {"source_text": "Title", "zh_reference": "标题", "render_text": "Title"}}
            data["status"] = "ready"
            path.write_text(json.dumps(data, ensure_ascii=False))
            result = self.validate_delivery(path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("directory_chain", result.stderr)
            slug = data["product_slug"]
            data["delivery"].update(
                directory_chain=[
                    {"name": "Agent A", "token": "fld_agent", "type": "folder", "parent_token": "root"},
                    {"name": "电商需求", "token": "fld_ecom", "type": "folder", "parent_token": "fld_agent"},
                    {"name": "Listing", "token": "fld_listing", "type": "folder", "parent_token": "fld_ecom"},
                    {"name": slug, "token": "fld_product", "type": "folder", "parent_token": "fld_listing"},
                ],
                product_folder_token="fld_product",
                folder={"token": "fld_product", "permalink": "https://docs.feishu.cn/drive/folder/fld_product"},
                docx={"token": "docx_token", "permalink": "https://docs.feishu.cn/docx/docx_token",
                      "docx_filename": f"{data['created_at'][:10].replace('-', '')}-{slug}-001.docx", "docx_batch": 1},
            )
            path.write_text(json.dumps(data, ensure_ascii=False))
            self.assertEqual(self.validate_delivery(path).returncode, 0)

    def test_card_rejects_fabricated_docx_directory_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.init(td, mode="card")
            data = json.loads(path.read_text())
            data["delivery"]["directory_chain"] = [{"name": "fake", "token": "fake_token", "type": "folder", "parent_token": "root"}]
            path.write_text(json.dumps(data))
            result = self.cli("validate", path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("card delivery must not contain", result.stderr)

    def test_force_rebuilds_v3_v4_v5_as_v6(self):
        with tempfile.TemporaryDirectory() as td:
            for version in (3, 4, 5):
                path = Path(td) / f"v{version}.json"
                path.write_text(json.dumps({"schema_version": version, "generation": 2, "revision": 4}))
                result = self.cli("init", path, "--force", "--delivery-mode", "card")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(path.read_text())["schema_version"], 6)


if __name__ == "__main__":
    unittest.main()
