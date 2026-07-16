import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_manifest.py"
MUTATIONS = {"set-facts","set-image-plan","add-replacement","add-replacement-slot","put-module","update-slot","set-qa","set-token","set-delivery","set-short-delivery-approval","timing","finalize"}

class FinalReviewSecurityTest(unittest.TestCase):
    def cli(self, *args, check=True, identity=True):
        args = list(map(str,args))
        if identity and args and args[0] in MUTATIONS and len(args)>1 and Path(args[1]).exists() and not any(x in args for x in ("--revision","--from-current")):
            d=json.loads(Path(args[1]).read_text())
            args += ["--manifest-id",d["manifest_id"],"--generation",str(d["generation"]),"--revision",str(d["revision"])]
        r=subprocess.run([sys.executable,str(CLI),*args],text=True,capture_output=True,env={**os.environ,"RUN_MANIFEST_APPROVAL_REGISTRY":str(Path(args[1]).parent/".approval-registry.json")} if len(args)>1 else None)
        if check and r.returncode:self.fail(r.stderr)
        return r
    def load(self,p):return json.loads(Path(p).read_text())
    def approval_args(self,p, count):
        expected=self.load(p)["expected_count"]
        return ("--provider","feishu","--channel","direct","--message-id","om_123456","--author-id","ou_123456","--approval-text",f"我明确批准当前 {expected}->{count} 短交付合同", "--captured-at","2026-07-15T15:00:00+00:00","--approved-count",count)

    def test_from_current_refuses_same_module_and_timing_field_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p)
            self.cli("put-module",p,"memo","--module-kind","internal","--json",'{"v":1}',"--from-current",identity=False)
            r=self.cli("put-module",p,"memo","--module-kind","internal","--json",'{"v":2}',"--from-current",identity=False,check=False)
            self.assertIn("already exists",r.stderr)
            self.cli("timing",p,"wave_0","--seconds",1,"--from-current",identity=False)
            r=self.cli("timing",p,"wave_0","--seconds",2,"--from-current",identity=False,check=False)
            self.assertIn("already exists",r.stderr)
            d=self.load(p);self.assertEqual(d["modules"]["memo"],{"v":1});self.assertEqual(d["timings"]["wave_0"]["seconds"],1)

    def test_short_contract_match_has_numeric_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",19,"--confirmed-by-user")
            for n in range(1,20):self.cli("update-slot",p,n,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            args=list(self.approval_args(p,0));args[args.index("--approval-text")+1]="我批准 9->0"
            r=self.cli("set-short-delivery-approval",p,*args,check=False)
            self.assertIn("19->0",r.stderr)

    def test_short_approval_registry_prevents_cross_manifest_reuse_and_failed_write_does_not_consume(self):
        with tempfile.TemporaryDirectory() as td:
            registry=Path(td)/"registry.json"
            def env_cli(*args,check=True):
                cmd=list(map(str,args));d=self.load(cmd[1]) if len(cmd)>1 and Path(cmd[1]).exists() else None
                if cmd[0] in MUTATIONS and d and not any(x in cmd for x in ("--revision","--from-current")):cmd += ["--manifest-id",d["manifest_id"],"--generation",str(d["generation"]),"--revision",str(d["revision"])]
                import os
                env={**os.environ,"RUN_MANIFEST_APPROVAL_REGISTRY":str(registry)}
                r=subprocess.run([sys.executable,str(CLI),*cmd],text=True,capture_output=True,env=env)
                if check and r.returncode:self.fail(r.stderr)
                return r
            p1=Path(td)/"one.json";p2=Path(td)/"two.json"
            for p in (p1,p2):
                env_cli("init",p,"--plan-mode","custom","--expected-count",1,"--confirmed-by-user")
                env_cli("update-slot",p,1,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            bad=list(self.approval_args(p1,0));bad[bad.index("--approval-text")+1]="wrong"
            self.assertNotEqual(env_cli("set-short-delivery-approval",p1,*bad,check=False).returncode,0)
            env_cli("set-short-delivery-approval",p1,*self.approval_args(p1,0))
            r=env_cli("set-short-delivery-approval",p2,*self.approval_args(p2,0),check=False)
            self.assertIn("already consumed",r.stderr)

    def test_approval_text_must_explicitly_name_current_n_to_m_contract(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",2,"--confirmed-by-user")
            for n in (1,2): self.cli("update-slot",p,n,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            args=list(self.approval_args(p,0));args[args.index("--approval-text")+1]="我批准 2->1"
            r=self.cli("set-short-delivery-approval",p,*args,check=False)
            self.assertIn("2->0",r.stderr)

    def test_approval_evidence_digest_and_final_hash_bind_every_field(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",1,"--confirmed-by-user")
            self.cli("update-slot",p,1,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.cli("set-short-delivery-approval",p,*self.approval_args(p,0))
            original=self.load(p)
            self.assertEqual(original["short_delivery_approval"]["evidence"]["actual_count"],0)
            self.assertEqual(len(original["short_delivery_approval"]["evidence_digest"]),64)
            for field,value in (("author_id","ou_forged"),("provider","otherxx"),("approval_text","批准 1->1"),("actual_count",1)):
                d=json.loads(json.dumps(original));d["short_delivery_approval"]["evidence"][field]=value
                q=Path(td)/f"{field}.json";q.write_text(json.dumps(d))
                self.assertIn("digest",self.cli("validate",q,check=False).stderr)

    def test_market_default_han_policy_is_fail_closed_except_japan(self):
        with tempfile.TemporaryDirectory() as td:
            fr=Path(td)/"fr.json";self.cli("init",fr,"--market","FR")
            r=self.cli("set-image-plan",fr,"--json",'[{"slot":1,"prompt":"高端广告","render_text":"veste"}]',check=False)
            self.assertIn("Han",r.stderr)
            jp=Path(td)/"jp.json";self.cli("init",jp,"--market","JP")
            self.cli("set-image-plan",jp,"--json",'[{"slot":1,"prompt":"高品質な広告","render_text":"商品"}]')

    def test_non_chinese_han_prompt_rejected_but_japanese_kanji_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"bad.json";self.cli("init",bad,"--target-language","fr")
            r=self.cli("set-image-plan",bad,"--json",'[{"slot":1,"prompt":"高端中文广告图","zh_reference":"轻便防水夹克","render_text":"veste"}]',check=False)
            self.assertIn("Han",r.stderr)
            ja=Path(td)/"ja.json";self.cli("init",ja,"--target-language","ja")
            self.cli("set-image-plan",ja,"--json",'[{"slot":1,"prompt":"高品質な商品広告","zh_reference":"轻便防水夹克","render_text":"商品広告"}]')

    def test_localization_approval_shapes_fields_and_timestamps_are_deeply_validated(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p)
            base=self.load(p)
            cases=[]
            for field in ("localization_policy","target_only_approval"):
                d=json.loads(json.dumps(base))
                if field=="localization_policy":d[field]["override"]="bad"
                else:d[field]="bad"
                cases.append(d)
            d=json.loads(json.dumps(base));d["localization_policy"]["override"]={"approved_by":1,"confirmation_text":[],"recorded_at":"yesterday"};cases.append(d)
            for i,d in enumerate(cases):
                q=Path(td)/f"policy{i}.json";q.write_text(json.dumps(d))
                self.assertNotEqual(self.cli("validate",q,check=False).returncode,0)

    def test_closed_schema_rejects_scalar_nested_nodes_and_unknown_approval_key(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p)
            base=self.load(p)
            mutations=[lambda d:d["module_contracts"].update(title={"kind":"docx_text"}),
                       lambda d:d["module_contracts"].update(title="bogus"),
                       lambda d:d["tokens"].update({"1":"scalar"}),
                       lambda d:d["images"][0].update(provider_error="timeout")]
            for i,f in enumerate(mutations):
                d=json.loads(json.dumps(base));f(d);q=Path(td)/f"shape{i}.json";q.write_text(json.dumps(d))
                self.assertNotEqual(self.cli("validate",q,check=False).returncode,0)
            d=json.loads(json.dumps(base));d["short_delivery_approval"]={"evil":1};q=Path(td)/"approval.json";q.write_text(json.dumps(d))
            self.assertIn("unknown",self.cli("validate",q,check=False).stderr)

    def test_corrupt_replacement_lineage_is_structurally_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",1,"--confirmed-by-user")
            self.cli("update-slot",p,1,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.cli("add-replacement",p,"--replaces-slot",1)
            base=self.load(p)
            for field,value in (("attempt",99),("predecessor_slot",999),("replaces_slot",2)):
                d=json.loads(json.dumps(base));d["images"][1][field]=value;q=Path(td)/f"lineage-{field}.json";q.write_text(json.dumps(d))
                self.assertIn("lineage",self.cli("validate",q,check=False).stderr)

    def test_requested_modules_must_be_predeclared_not_self_declared_by_put(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--task-scope","content","--requested-module","title","--requested-module","bullets")
            self.cli("put-module",p,"title","--json",'{"source_text":"Titre","zh_reference":"标题","render_text":"Titre"}')
            d=self.load(p)
            self.assertEqual(d["requested_docx_modules"],["title","bullets"])
            self.assertNotEqual(self.cli("validate",p,check=False).returncode,0)
            r=self.cli("put-module",p,"undeclared","--json",'{"source_text":"X","zh_reference":"中文","render_text":"X"}',check=False)
            self.assertIn("predeclared",r.stderr)

    def test_mutation_identity_is_all_or_none_and_required_for_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p)
            r=self.cli("set-facts",p,"--json",'{"market":"TH"}',identity=False,check=False)
            self.assertIn("manifest_id",r.stderr)
            d=self.load(p)
            r=self.cli("set-facts",p,"--json",'{"market":"TH"}',"--revision",d["revision"],identity=False,check=False)
            self.assertIn("all be provided",r.stderr)

    def test_short_approval_requires_message_evidence_is_immutable_and_manifest_bound(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",2,"--confirmed-by-user")
            self.cli("update-slot",p,1,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.cli("update-slot",p,2,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            r=self.cli("set-short-delivery-approval",p,"--approved-count",0,check=False)
            self.assertNotEqual(r.returncode,0)
            self.cli("set-short-delivery-approval",p,*self.approval_args(p,0))
            a=self.load(p)["short_delivery_approval"]
            self.assertEqual(a["contract"]["manifest_id"],self.load(p)["manifest_id"])
            self.assertEqual(a["contract"]["rejected_slots"],[1,2])
            self.assertEqual(len(a["contract_hash"]),64)
            r=self.cli("set-short-delivery-approval",p,*self.approval_args(p,0),check=False)
            self.assertIn("immutable",r.stderr)
            d=self.load(p);d["manifest_id"]="cross-manifest";p.write_text(json.dumps(d))
            self.assertNotEqual(self.cli("validate",p,check=False).returncode,0)

    def test_approval_replay_after_set_change_and_unconsumed_ready_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",2,"--confirmed-by-user")
            for n in (1,2):self.cli("update-slot",p,n,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.cli("set-short-delivery-approval",p,*self.approval_args(p,0))
            d=self.load(p);d["delivery"]["rejected_slots"]=[2,1];d["status"]="ready";p.write_text(json.dumps(d))
            r=self.cli("validate",p,"--delivery",check=False)
            self.assertRegex(r.stderr,"consumed|contract|finalized")

    def test_prompt_leakage_detects_sibling_fragment_nested_and_target_only_reference(self):
        cases=[
          '[{"slot":1,"zh_reference":"轻便防水夹克","render_text":"veste","prompt":"photo 轻便防水 premium"}]',
          '[{"slot":1,"zh_reference":"轻便防水夹克","render_text":"veste","prompt":{"nested":{"prompt":"studio 防水夹克"}}}]']
        with tempfile.TemporaryDirectory() as td:
            for i,payload in enumerate(cases):
                p=Path(td)/f"r{i}.json";self.cli("init",p)
                self.assertIn("prompt",self.cli("set-image-plan",p,"--json",payload,check=False).stderr)
            p=Path(td)/"mono.json";self.cli("init",p,"--task-scope","content","--target-language","fr","--monolingual","--monolingual-confirmation","French only","--requested-module","title")
            r=self.cli("put-module",p,"title","--json",'{"source_text":"fr","render_text":"fr","zh_reference":"中文"}',check=False)
            self.assertIn("zh_reference",r.stderr)

    def test_recursive_closed_schema_rejects_nested_unknowns(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p)
            mutations=[
              lambda d:d["delivery"]["card"].update(evil=True),
              lambda d:d["images"][0].update(evil=True),
              lambda d:d["images"][0].update(provider_error={"code":"timeout","evil":1}),
              lambda d:d["qa"].update(evil=True),
              lambda d:d["facts"].update(evil=True),
              lambda d:d["timings"].update(evil={"seconds":1}),
              lambda d:d.update(evil=True)]
            for i,f in enumerate(mutations):
                d=self.load(p);f(d);q=Path(td)/f"bad{i}.json";q.write_text(json.dumps(d))
                self.assertIn("unknown",self.cli("validate",q,check=False).stderr)

    def test_force_rebuilds_schema_v3_without_v4_validation_but_rejects_bad_identity_types(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json"
            p.write_text(json.dumps({"schema_version":3,"generation":7,"revision":12,"legacy":"anything"}))
            self.cli("init",p,"--force")
            d=self.load(p);self.assertEqual((d["schema_version"],d["generation"],d["revision"]),(4,8,13))
            for field,value in (("generation",True),("revision","12"),("generation",0),("revision",-1)):
                p.write_text(json.dumps({"schema_version":3,"generation":7,"revision":12,field:value}))
                r=self.cli("init",p,"--force",check=False)
                self.assertNotEqual(r.returncode,0)

    def test_file_containment_rejects_absolute_parent_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root=Path(td);p=root/"run.json";self.cli("init",p)
            ext=Path(outside)/"x.png";ext.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            (root/"link.png").symlink_to(ext)
            for value in (str(ext),"../outside.png","link.png"):
                self.cli("update-slot",p,1,"--json",json.dumps({"status":"success","file":value,"qa_label":"green"}))
                self.assertIn("run_root",self.cli("validate",p,check=False).stderr)
            good=root/"ok.png";good.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            self.cli("update-slot",p,1,"--json",'{"file":"ok.png"}')
            self.assertEqual(self.cli("validate",p,check=False).returncode,0)

    def test_replacement_lineage_orders_multiple_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"run.json";self.cli("init",p,"--plan-mode","custom","--expected-count",1,"--confirmed-by-user")
            self.cli("update-slot",p,1,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.cli("add-replacement",p,"--replaces-slot",1)
            self.cli("update-slot",p,2,"--json",'{"status":"rejected","qa_label":"red","hard_reject_reason":"off_topic"}')
            self.cli("add-replacement",p,"--replaces-slot",1)
            slots=self.load(p)["images"]
            self.assertEqual([(x["attempt"],x["predecessor_slot"]) for x in slots],[(1,None),(2,1),(3,2)])

if __name__=="__main__":unittest.main()
