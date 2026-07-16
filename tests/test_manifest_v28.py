import json
import subprocess
import sys
import tempfile
import os
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"
sys.path.insert(0, str(ROOT / "scripts"))
import run_manifest


class ManifestV28Test(unittest.TestCase):
    def run_cli(self, *args, check=True):
        args=list(map(str,args))
        mutations={"set-facts","set-image-plan","add-replacement","add-replacement-slot","put-module","update-slot","set-qa","set-token","set-delivery","set-short-delivery-approval","timing","finalize"}
        if args and args[0] in mutations and len(args)>1 and Path(args[1]).exists() and "--from-current" not in args:
            data=self.load(args[1])
            if "--revision" not in args:args += ["--revision",str(data["revision"])]
            if "--manifest-id" not in args:args += ["--manifest-id",data["manifest_id"]]
            if "--generation" not in args:args += ["--generation",str(data["generation"])]
        result = subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True, env={**os.environ,"RUN_MANIFEST_APPROVAL_REGISTRY":str(Path(args[1]).parent/".approval-registry.json")} if len(args)>1 else None)
        if check and result.returncode:
            self.fail(result.stderr or result.stdout)
        return result

    def load(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def make_card_delivery_evidence(self, path):
        data = self.load(path)
        deliverable = [x["slot"] for x in data["images"] if x.get("status") == "success"]
        rejected = [x["slot"] for x in data["images"] if x.get("status") == "rejected"]
        data["delivery_mode"] = "card"
        data["tokens"] = {str(n): {"image_key": f"image_key_{n}"} for n in deliverable}
        data["delivery"] = {"deliverable_slots": deliverable, "rejected_slots": rejected,
                            "docx": {"token": None, "permalink": None}, "folder": {"permalink": None},
                            "card": {"message_id": "message_fixture", "send_success": True}}
        final_slots = deliverable + rejected
        data["qa"] = {"mode": f"{data['expected_count']}-image-single-round", "reviewed_at": "2026-07-15T12:00:00+00:00",
                      "reviewed_slot_ids": final_slots, "reviewed_count": len(final_slots)}
        data["timings"] = {stage: {"seconds": 1.0} for stage in ("wave_0", "wave_1", "wave_2", "total")}
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_default_full_has_nine_slots_and_contract_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            data = self.load(path)
            self.assertEqual(data["schema_version"], 4)
            self.assertEqual(data["revision"], 0)
            self.assertEqual(data["plan_mode"], "default_full")
            self.assertEqual(data["expected_count"], 9)
            self.assertEqual(len(data["images"]), 9)

    def test_custom_and_revision_create_dynamic_slots(self):
        for mode, count in (("custom", 3), ("revision", 1)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "run.json"
                self.run_cli("init", path, "--plan-mode", mode, "--expected-count", count, "--confirmed-by-user")
                data = self.load(path)
                self.assertEqual([x["slot"] for x in data["images"]], list(range(1, count + 1)))
                self.assertEqual(data["confirmed_by_user"], True)

    def test_custom_requires_explicit_count_and_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            for args in (("--plan-mode", "custom"), ("--plan-mode", "revision", "--expected-count", "2")):
                result = self.run_cli("init", path, *args, check=False)
                self.assertNotEqual(result.returncode, 0)

    def test_controlled_mutations_update_fields_and_revision(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            self.run_cli("set-facts", path, "--json", '{"market":"TH","language":"th"}', "--revision", 0)
            self.run_cli("set-image-plan", path, "--json", '[{"slot":1,"purpose":"hero"}]', "--revision", 1)
            self.run_cli("put-module", path, "title", "--json", '{"source_text":"รองเท้า","zh_reference":"鞋","render_text":"รองเท้า"}', "--revision", 2)
            data = self.load(path)
            self.assertEqual(data["revision"], 3)
            self.assertEqual(data["facts"]["language"], "th")
            self.assertEqual(data["images"][0]["purpose"], "hero")
            self.assertEqual(data["modules"]["title"]["render_text"], "รองเท้า")

    def test_revision_conflict_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            self.run_cli("set-facts", path, "--json", '{"market":"VN"}', "--revision", 0)
            result = self.run_cli("set-facts", path, "--json", '{"market":"TH"}', "--revision", 0, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("revision conflict", result.stderr)
            self.assertEqual(self.load(path)["facts"]["market"], "VN")

    def test_concurrent_writes_are_serialized_without_lost_updates(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            errors = []
            def worker(i):
                result = self.run_cli("put-module", path, f"m{i}", "--module-kind", "internal", "--json", json.dumps({"value": i}), "--from-current", check=False)
                if result.returncode: errors.append(result.stderr)
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertFalse(errors)
            data = self.load(path)
            self.assertEqual(len(data["modules"]), 12)
            self.assertEqual(data["revision"], 12)

    def test_concurrent_bilingual_docx_text_modules_remain_valid(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--task-scope", "content", "--market", "TH", *sum((["--requested-module", f"docx{i}"] for i in range(8)), []))
            errors = []
            def worker(i):
                payload = {"source_text": f"ข้อความ {i}", "zh_reference": f"中文 {i}", "render_text": f"ข้อความ {i}"}
                result = self.run_cli("put-module", path, f"docx{i}", "--module-kind", "docx_text", "--json", json.dumps(payload), "--from-current", check=False)
                if result.returncode: errors.append(result.stderr)
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertFalse(errors)
            data = self.load(path)
            self.assertEqual(len(data["requested_docx_modules"]), 8)
            self.run_cli("validate", path)

    def test_atomic_save_preserves_old_file_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            before = path.read_bytes()
            data = self.load(path); data["status"] = "changed"
            with mock.patch("run_manifest.os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError): run_manifest.atomic_save(path, data)
            self.assertEqual(path.read_bytes(), before)

    def test_add_replacement_creates_controlled_slot_with_lineage(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--plan-mode", "custom", "--expected-count", 2, "--confirmed-by-user")
            self.run_cli("update-slot", path, 1, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.run_cli("add-replacement", path, "--replaces-slot", 1, "--purpose", "replacement hero")
            data = self.load(path)
            self.assertEqual(data["expected_count"], 2)
            self.assertEqual(data["images"][-1]["slot"], 3)
            self.assertEqual(data["images"][-1]["replaces_slot"], 1)
            self.assertEqual(data["images"][-1]["purpose"], "replacement hero")
            self.run_cli("validate", path)

    def test_replacement_requires_existing_contracted_or_rejected_slot(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            for value in (True, 99):
                result = self.run_cli("add-replacement", path, "--replaces-slot", value, check=False)
                self.assertNotEqual(result.returncode, 0)

    def test_finalize_requires_n_of_n_unless_explicit_short_override(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--plan-mode", "custom", "--expected-count", 2, "--confirmed-by-user")
            image = Path(td) / "one.png"; image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.run_cli("update-slot", path, 1, "--json", json.dumps({"status":"success", "file":str(image), "qa_label":"green"}))
            result = self.run_cli("finalize", path, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.run_cli("update-slot", path, 2, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.make_card_delivery_evidence(path)
            self.run_cli("set-short-delivery-approval", path, "--provider", "feishu", "--channel", "direct", "--message-id", "om_fixture", "--author-id", "ou_fixture", "--approval-text", "User explicitly approves current 2->1 short-delivery contract", "--captured-at", "2026-07-15T12:00:00+00:00", "--approved-count", 1)
            self.run_cli("finalize", path)
            final = self.load(path)
            self.assertEqual(final["status"], "ready")
            self.assertEqual(final["short_delivery_approval"]["evidence"]["provider"], "feishu")

    def test_free_text_override_is_removed_and_pending_cannot_finalize(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pending.json"
            self.run_cli("init", path, "--plan-mode", "custom", "--expected-count", 2, "--confirmed-by-user")
            result = self.run_cli("finalize", path, "--short-delivery-override", "free text", check=False)
            self.assertIn("unrecognized arguments", result.stderr)
            result = self.run_cli("finalize", path, check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_override_accepts_final_rejected_contracted_slot_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--plan-mode", "custom", "--expected-count", 2, "--confirmed-by-user")
            image = Path(td) / "one.png"; image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.run_cli("update-slot", path, 1, "--json", json.dumps({"status":"success", "file":str(image), "qa_label":"green"}))
            self.run_cli("update-slot", path, 2, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.make_card_delivery_evidence(path)
            self.run_cli("set-short-delivery-approval", path, "--provider", "feishu", "--channel", "direct", "--message-id", "om_fixture", "--author-id", "ou_fixture", "--approval-text", "User explicitly approves current 2->1 short-delivery contract", "--captured-at", "2026-07-15T12:00:00+00:00", "--approved-count", 1)
            self.run_cli("finalize", path)
            self.assertEqual(self.load(path)["status"], "ready")

    def test_malformed_shapes_report_without_traceback(self):
        malformed = [[], {"images":[None]}, {"modules":[]}, {"tokens":[]}, {"qa":[]}, {"delivery":[]}, {"timings":[]}]
        with tempfile.TemporaryDirectory() as td:
            for index, mutation in enumerate(malformed):
                path = Path(td) / f"bad-{index}.json"
                self.run_cli("init", path)
                if index == 0:
                    path.write_text("[]", encoding="utf-8")
                else:
                    data = self.load(path); data.update(mutation); path.write_text(json.dumps(data), encoding="utf-8")
                for command in (("validate", path), ("select-retry", path)):
                    result = self.run_cli(*command, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)

    def test_bool_slot_and_slot_identity_patches_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            result = self.run_cli("set-image-plan", path, "--json", '[{"slot":true,"purpose":"bad"}]', check=False)
            self.assertNotEqual(result.returncode, 0)
            result = self.run_cli("set-image-plan", path, "--json", '[{"slot":1,"replaces_slot":2}]', check=False)
            self.assertNotEqual(result.returncode, 0)
            result = self.run_cli("update-slot", path, True, "--json", '{"status":"failed"}', check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_mutation_validates_candidate_before_save(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            before = path.read_bytes()
            result = self.run_cli("set-qa", path, "--json", '{"mode":[]}', check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), before)

    def test_relative_image_path_resolves_from_manifest_directory(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            directory = Path(td); path = directory / "run.json"
            image = directory / "relative.png"; image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.run_cli("init", path)
            self.run_cli("update-slot", path, 1, "--json", '{"status":"success","file":"relative.png","qa_label":"green"}')
            result = subprocess.run([sys.executable, str(CLI), "validate", str(path)], cwd=other, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_force_increments_revision_generation_changes_id_and_stale_identity_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            old = self.load(path)
            self.run_cli("set-facts", path, "--json", '{"market":"VN"}')
            self.run_cli("init", path, "--force")
            new = self.load(path)
            self.assertEqual(new["revision"], 2)
            self.assertEqual(new["generation"], old["generation"] + 1)
            self.assertNotEqual(new["manifest_id"], old["manifest_id"])
            result = self.run_cli("set-facts", path, "--json", '{"market":"TH"}',
                                  "--revision", new["revision"], "--manifest-id", old["manifest_id"],
                                  "--generation", old["generation"], check=False)
            self.assertIn("manifest identity conflict", result.stderr)

    def test_atomic_save_preserves_existing_mode_and_reads_only_magic_header(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            os.chmod(path, 0o640)
            data = self.load(path); data["status"] = "changed"
            run_manifest.atomic_save(path, data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            image = Path(td) / "large.png"; image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 1024)
            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("must not read whole file")):
                self.assertTrue(run_manifest.has_supported_image_magic(image, Path(td)))

    def test_updater_exception_and_replace_failure_preserve_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path); before = path.read_bytes()
            with self.assertRaises(RuntimeError):
                run_manifest.mutate(path, lambda data: (_ for _ in ()).throw(RuntimeError("updater")))
            self.assertEqual(path.read_bytes(), before)
            with mock.patch("run_manifest.os.replace", side_effect=OSError("replace")):
                with self.assertRaises(OSError): run_manifest.mutate(path, lambda data: data["facts"].update(notes="changed"))
            self.assertEqual(path.read_bytes(), before)

    def test_content_scope_has_zero_images_and_docx_only_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "content.json"
            self.run_cli("init", path, "--task-scope", "content", "--market", "FR", "--target-language", "fr", "--requested-module", "title")
            data = self.load(path)
            self.assertEqual(data["expected_count"], 0)
            self.assertEqual(data["images"], [])
            self.run_cli("put-module", path, "title", "--json", '{"source_text":"Titre","zh_reference":"标题","render_text":"Titre"}')
            self.run_cli("set-delivery", path, "--json", '{"docx":{"token":"docx_fixture","permalink":"https://docs.feishu.cn/docx/fixture"},"folder":{"permalink":"https://docs.feishu.cn/drive/folder/fixture"}}')
            self.run_cli("finalize", path)
            self.run_cli("validate", path, "--delivery")
            self.assertEqual(self.load(path)["delivery"]["card"]["send_success"], False)

    def test_image_and_full_scopes_keep_image_contract(self):
        for scope in ("image", "full"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "run.json"
                self.run_cli("init", path, "--task-scope", scope)
                data = self.load(path)
                self.assertEqual(data["expected_count"], 9)
                self.assertEqual(len(data["images"]), 9)

    def test_replacement_requires_rejected_contracted_slot_and_one_active_final(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--task-scope", "image", "--plan-mode", "custom", "--expected-count", 1, "--confirmed-by-user")
            result = self.run_cli("add-replacement-slot", path, "--replaces-slot", 1, check=False)
            self.assertIn("rejected contracted slot", result.stderr)
            self.run_cli("update-slot", path, 1, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.run_cli("add-replacement-slot", path, "--replaces-slot", 1)
            result = self.run_cli("add-replacement-slot", path, "--replaces-slot", 1, check=False)
            self.assertIn("active final replacement", result.stderr)

    def test_contract_coverage_counts_replacement_not_global_success(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--task-scope", "image", "--plan-mode", "custom", "--expected-count", 1, "--confirmed-by-user", "--delivery-mode", "card")
            self.run_cli("update-slot", path, 1, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.run_cli("add-replacement-slot", path, "--replaces-slot", 1)
            image = Path(td) / "replacement.png"; image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.run_cli("update-slot", path, 2, "--json", json.dumps({"status":"success","file":str(image),"qa_label":"green"}))
            data = self.load(path)
            data["tokens"] = {"2":{"image_key":"image_key_2"}}
            data["delivery"] = {"deliverable_slots":[2],"rejected_slots":[1],"docx":{"token":None,"permalink":None},"folder":{"permalink":None},"card":{"message_id":"message_fixture","send_success":True}}
            data["qa"] = {"mode":"1-image-single-round","reviewed_at":"2026-07-15T12:00:00+00:00","reviewed_slot_ids":[1,2],"reviewed_count":2}
            data["timings"] = {x:{"seconds":1} for x in ("wave_0","wave_1","wave_2","total")}
            path.write_text(json.dumps(data), encoding="utf-8")
            self.run_cli("finalize", path)
            self.run_cli("validate", path, "--delivery")

    def test_short_delivery_requires_preexisting_structured_user_approval(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--task-scope", "image", "--plan-mode", "custom", "--expected-count", 2, "--confirmed-by-user")
            self.run_cli("update-slot", path, 1, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.run_cli("update-slot", path, 2, "--json", '{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            result = self.run_cli("finalize", path, "--short-delivery-override", "free text", check=False)
            self.assertNotEqual(result.returncode, 0)
            result = self.run_cli("set-short-delivery-approval", path, "--provider", "x", "--channel", "x", "--message-id", "x", "--author-id", "x", "--approved-count", 0, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.run_cli("set-short-delivery-approval", path, "--provider", "feishu", "--channel", "direct", "--message-id", "om_fixture", "--author-id", "ou_fixture", "--approval-text", "User explicitly approves current 2->0 short-delivery contract", "--captured-at", "2026-07-15T12:00:00+00:00", "--approved-count", 0)
            self.make_card_delivery_evidence(path)
            self.run_cli("finalize", path)
            approval = self.load(path)["short_delivery_approval"]
            self.assertEqual(approval["contract"]["expected_count"], 2)
            self.assertEqual(approval["evidence"]["provider"], "feishu")

    def test_bilingual_manifest_defaults_and_target_only_requires_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            foreign = Path(td) / "foreign.json"
            self.run_cli("init", foreign, "--task-scope", "content", "--target-language", "fr")
            self.assertEqual(self.load(foreign)["docx_language_mode"], "bilingual")
            result = self.run_cli("init", Path(td)/"mono.json", "--task-scope", "content", "--target-language", "fr", "--docx-language-mode", "target_only", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.run_cli("init", Path(td)/"mono-ok.json", "--task-scope", "content", "--target-language", "fr", "--docx-language-mode", "target_only", "--target-only-approved-by-user", "--target-only-confirmation", "User requested French only")
            chinese = Path(td)/"zh.json"
            self.run_cli("init", chinese, "--task-scope", "content", "--target-language", "zh-CN")
            self.assertEqual(self.load(chinese)["docx_language_mode"], "chinese")

    def test_full_non_chinese_delivery_rejects_plain_dict_module_and_empty_zh(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"full.json"
            self.run_cli("init", path, "--task-scope", "full", "--target-language", "fr", "--requested-module", "title")
            result = self.run_cli("put-module", path, "title", "--json", '{"headline":"Titre"}', check=False)
            self.assertNotEqual(result.returncode, 0)
            result = self.run_cli("put-module", path, "title", "--json", '{"source_text":"Titre","zh_reference":"   ","render_text":"Titre"}', check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_all_text_mutations_reject_zh_leak_into_prompt_or_render(self):
        cases = [
            ("set-facts", ["--json", '{"copy":{"source_text":"FR","zh_reference":"中文","render_text":"FR 中文"}}']),
            ("set-image-plan", ["--json", '[{"slot":1,"prompt":{"source_text":"FR","zh_reference":"中文","render_text":"FR 中文"}}]']),
            ("update-slot", ["1", "--json", '{"prompt":{"source_text":"FR","zh_reference":"中文","render_text":"FR 中文"}}']),
        ]
        with tempfile.TemporaryDirectory() as td:
            for command, args in cases:
                path=Path(td)/f"{command}.json"; self.run_cli("init",path)
                result=self.run_cli(command,path,*args,check=False)
                self.assertIn("zh_reference",result.stderr)

    def test_mutation_allowlists_fail_closed_and_stale_same_slot_revision_conflicts(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"run.json"; self.run_cli("init",path)
            for payload in ('{"status":"success"}','{"file":"x.png"}','{"qa_label":"green"}'):
                result=self.run_cli("set-image-plan",path,"--json",f'[{{"slot":1,{payload[1:]}]',check=False)
                self.assertNotEqual(result.returncode,0)
            self.run_cli("update-slot",path,1,"--json",'{"purpose":"first"}',"--revision",0)
            result=self.run_cli("update-slot",path,1,"--json",'{"purpose":"stale"}',"--revision",0,check=False)
            self.assertIn("revision conflict",result.stderr)

    def test_qa_requires_timezone_and_exact_reviewed_slot_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"run.json"; self.run_cli("init",path)
            for reviewed_at in ("2026-07-15", "2026-07-15T12:00:00"):
                result=self.run_cli("set-qa",path,"--json",json.dumps({"reviewed_at":reviewed_at,"reviewed_slot_ids":[],"reviewed_count":0}),check=False)
                self.assertNotEqual(result.returncode,0)

    def test_market_only_non_chinese_content_defaults_to_bilingual_policy(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "th.json"
            self.run_cli("init", path, "--task-scope", "content", "--market", "TH", "--requested-module", "title")
            policy = self.load(path)["localization_policy"]
            self.assertEqual(policy["docx_language_mode"], "bilingual")
            self.assertEqual(policy["basis"], "non_chinese_market_default")
            result = self.run_cli("put-module", path, "title", "--module-kind", "docx_text", "--json", '{"title":"Thai only"}', check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("zh_reference", result.stderr)

    def test_docx_text_internal_and_nontext_modules_have_distinct_contracts(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path, "--task-scope", "content", "--market", "TH")
            self.run_cli("put-module", path, "internal_notes", "--module-kind", "internal", "--json", '{"status":"draft"}')
            self.run_cli("put-module", path, "metrics", "--module-kind", "non_text", "--json", '{"count":3}')
            data = self.load(path)
            self.assertEqual(data["module_contracts"]["internal_notes"], "internal")
            self.assertEqual(data["module_contracts"]["metrics"], "non_text")
            self.assertNotIn("internal_notes", data["requested_docx_modules"])

    def test_monolingual_override_is_structured_and_chinese_market_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.run_cli("init", Path(td)/"bad.json", "--task-scope", "content", "--market", "TH", "--monolingual", check=False)
            self.assertNotEqual(result.returncode, 0)
            mono = Path(td)/"mono.json"
            self.run_cli("init", mono, "--task-scope", "content", "--market", "TH", "--monolingual", "--monolingual-confirmation", "User requested Thai only", "--requested-module", "title")
            policy = self.load(mono)["localization_policy"]
            self.assertEqual(policy["docx_language_mode"], "target_only")
            self.assertEqual(policy["override"]["approved_by"], "user")
            self.run_cli("put-module", mono, "title", "--module-kind", "docx_text", "--json", '{"source_text":"ไทย","render_text":"ไทย"}')
            zh = Path(td)/"zh.json"
            self.run_cli("init", zh, "--task-scope", "content", "--market", "CN", "--requested-module", "title")
            self.assertEqual(self.load(zh)["localization_policy"]["docx_language_mode"], "chinese")
            self.run_cli("put-module", zh, "title", "--module-kind", "docx_text", "--json", '{"source_text":"中文标题","render_text":"中文标题"}')

    def test_final_validation_rechecks_only_requested_docx_text_modules(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"run.json"
            self.run_cli("init", path, "--task-scope", "content", "--market", "TH", "--requested-module", "title")
            self.run_cli("put-module", path, "title", "--module-kind", "docx_text", "--json", '{"source_text":"ไทย","zh_reference":"中文","render_text":"ไทย"}')
            self.run_cli("put-module", path, "internal", "--module-kind", "internal", "--json", '{"plain":"allowed"}')
            data=self.load(path); data["modules"]["title"]={"title":"bypass"}; path.write_text(json.dumps(data),encoding="utf-8")
            result=self.run_cli("validate",path,check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("modules.title",result.stderr)

    def test_text_fields_keep_reference_out_of_render_text(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "run.json"
            self.run_cli("init", path)
            good = '{"source_text":"รองเท้า","zh_reference":"鞋子","render_text":"รองเท้า"}'
            self.run_cli("put-module", path, "copy", "--json", good)
            bad = '{"source_text":"รองเท้า","zh_reference":"鞋子","render_text":"รองเท้า 鞋子"}'
            result = self.run_cli("put-module", path, "bad", "--json", bad, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("zh_reference", result.stderr)


if __name__ == "__main__":
    unittest.main()
