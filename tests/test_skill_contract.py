import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["SKILL.md", "QUALITY_GATE.md", "OUTPUT_TEMPLATE.md"]


class SkillContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.gate = (ROOT / "QUALITY_GATE.md").read_text(encoding="utf-8")
        cls.template = (ROOT / "OUTPUT_TEMPLATE.md").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_frontmatter_uses_current_metadata_shape(self):
        match = re.match(r"^---\n(.*?)\n---\n", self.skill, re.S)
        self.assertIsNotNone(match)
        frontmatter = match.group(1)
        self.assertRegex(frontmatter, r"(?m)^name: ecommerce-product-listing-skill$")
        self.assertRegex(frontmatter, r'(?m)^description: "Use when .*"$')
        self.assertNotRegex(frontmatter, r'(?m)^description: .*v2\.8\.0')
        self.assertNotRegex(frontmatter, r"(?m)^version:")
        self.assertRegex(frontmatter, r"(?m)^metadata:\n  version: \"2\.12\.0\"$")

    def test_markdown_fences_are_balanced(self):
        for name in DOCS + ["README.md", "CHANGELOG.md"]:
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(text.count("```") % 2, 0, name)

    def test_version_is_consistent(self):
        for name, text in [("SKILL", self.skill), ("README", self.readme), ("CHANGELOG", self.changelog)]:
            self.assertRegex(text, r"v?2\.12\.0", name)

    def test_default_full_is_nine_images_but_custom_count_is_dynamic(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        self.assertIn("default_full", joined)
        self.assertIn("expected_count", joined)
        self.assertIn("custom", joined)
        self.assertIn("revision", joined)
        self.assertIn("默认完整方案 9 张", joined)
        self.assertNotIn("9 槽位必须", joined)

    def test_quality_red_lines_remain(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        required = [
            "图生图", "参考图池全传", "Pre-QA", "三段式", "默认真人",
            "Docx", "图文卡片", "file_token", "image_key", "生成失败", "直接交付",
        ]
        for phrase in required:
            self.assertIn(phrase, joined, phrase)

    def test_pipeline_and_incremental_recovery_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        for phrase in ["Wave 0", "Wave 1", "Wave 2", "单一事实源", "合并确认关口", "单槽位重试", "禁止整批重跑", "按序号直接交付", "同一 Docx 写操作有序"]:
            self.assertIn(phrase, joined, phrase)

    def test_capability_preflight_preserves_supported_flag(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        self.assertIn("版本对齐", joined)
        self.assertIn("capability preflight", joined)
        self.assertIn("--selection-with-ellipsis", joined)

    def test_current_rule_semantics_are_explicit_and_legacy_conflicts_absent(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        self.assertRegex(joined, r"image-provider-gateway.{0,120}`?>= 0\.1\.0")
        self.assertNotRegex("\n".join([self.skill, self.gate]), r"image-provider-gateway.{0,120}`?>= 0\.2\.0")
        self.assertIn("手拼 batch JSON 或 shell 单行", joined)
        self.assertIn("不作硬门槛", joined)
        self.assertIn("生成成功", joined)
        self.assertIn("生成失败", joined)
        self.assertNotIn("🟡 图未带\"修复方式建议\"字段", joined)
        self.assertNotIn("逐张做 Post-QA", joined)
        self.assertNotIn("--concurrency 3", joined)

    def test_core_relaxations_remain_without_version_history_narrative(self):
        joined = "\n".join([self.skill, self.gate, self.readme, self.changelog])
        for phrase in [
"Variant-Preservation Block", "不作硬门槛", "不设硬字符阈值",
            "ASCII 双引号会自动转义", "生成失败",
        ]:
            self.assertIn(phrase, joined, phrase)

    def test_mutation_examples_carry_full_identity(self):
        joined="\n".join([self.skill,self.gate,self.template,self.readme])
        self.assertIn("manifest_mutate()",self.template)
        for phrase in ("--manifest-id", "--generation", "--revision", "schema"):
            self.assertIn(phrase,joined)
        self.assertNotIn("RUN_MANIFEST_APPROVAL_REGISTRY",joined)

    def test_manifest_final_acceptance_evidence_is_documented(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in [
            "failed_slots", "wave_0", "wave_1", "wave_2",
            "total", "PNG/JPEG/WebP/GIF", "success", "failed",
        ]:
            self.assertIn(phrase, joined, phrase)
        self.assertNotIn("详见 SKILL §5 步骤 5", self.gate)
        self.assertIn("expected_count", joined)
        self.assertNotIn("set-short-delivery-approval", joined)
        self.assertNotIn("short_delivery_override", joined)

    def test_v212_persistent_delivery_routing_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in ["scripts/delivery_config.py", "bootstrap", "status", "resolve", "record-success", "invalidate", "skill_config", "explicit_user_override", "--delivery-config", "schema v8"]:
            self.assertIn(phrase, joined, phrase)
        for phrase in ["配置缺失", "配置损坏", "版本不兼容", "实际调用", "用户明确确认", "不得重复", "禁止静默降级"]:
            self.assertIn(phrase, joined, phrase)
        for route in ["docx", "interactive_card", "preview_images"]:
            self.assertIn(route, joined, route)
        self.assertNotIn("--delivery-mode", joined)
        self.assertNotRegex(joined, r"(?<!interactive_)\bcard 模式")

    def test_delivery_modes_and_docx_batch_rule_are_consistent(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in ["docx", "interactive_card", "failed_slots", "生成失败"]:
            self.assertIn(phrase, joined, phrase)
        self.assertNotIn("每次跑 Skill 都 +1", joined)
        self.assertNotIn("每次跑都 +1", joined)

    def test_quality_gate_heading_numbers_are_unique_and_nested(self):
        headings = re.findall(r"^(#{2,3}) (\d+(?:\.\d+)?)\b", self.gate, re.M)
        level_two = [number for hashes, number in headings if hashes == "##"]
        self.assertEqual(level_two, [str(number) for number in range(1, 17)])
        self.assertEqual(len(level_two), len(set(level_two)))
        for hashes, number in headings:
            if hashes == "###":
                self.assertIn(number.split(".")[0], level_two)

    def test_history_is_kept_in_changelog_not_operational_docs(self):
        self.assertNotRegex(self.skill, r"(?m)^## .*v2\.[0-9]")
        self.assertIn("v2.9.0", self.changelog)

    def test_bilingual_docx_and_prompt_text_separation_are_explicit(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        for phrase in ["source_text", "zh_reference", "render_text", "逐项紧邻中文对照", "中文对照不得传入生图 prompt", "显式要求单语"]:
            self.assertIn(phrase, joined, phrase)

    def test_auxiliary_files_are_loaded_conditionally(self):
        self.assertIn("按任务条件读取", self.skill)
        self.assertNotIn("强制扩展规则", self.skill)

    def test_v210_directory_and_identity_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in ["/{agent_name}/电商需求/Listing/{slug}/", "IDENTITY.md", "名字", "hard fail", "逐层", "name", "type", "parent"]:
            self.assertIn(phrase, joined, phrase)
        self.assertIn("open_id", joined)
        self.assertIn("agent id", joined)

    def test_v210_slug_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        for phrase in ["品牌型号原样", "ISO 3166-1 alpha-2", "whitespace", "折叠", "剥离", "具体产品名/型号", "颜色", "语言", "包装", "SKU", "retry", "revision", "日期", "跨天", "返工", "复用"]:
            self.assertIn(phrase, joined, phrase)

    def test_v210_empty_token_and_json_capture_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        for phrase in ["非空", "占位", "root fallback", "stderr", "JSON"]:
            self.assertIn(phrase, joined, phrase)

    def test_v210_asset_and_batch_naming_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        for phrase in ["MainNNN-NN", "YYYYMMDD-{slug}-NNN", "独立批次", "返工只修改点名槽位批次", "新文档按每槽位当前最新成功资产", "生成失败", "SKU 仅在用户明说时使用"]:
            self.assertIn(phrase, joined, phrase)
        self.assertNotIn("replacement", "\n".join([self.skill, self.gate, self.template, self.readme]))

    def test_v210_manifest_v6_directory_evidence_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in ["schema v8", "agent_name", "product_slug", "market_country_code", "drive_path_segments", "delivery.directory_chain", "delivery.product_folder_token", "delivery.folder.permalink", "delivery.docx.docx_filename", "delivery.docx.docx_batch", "images[].asset_filename", "images[].image_batch"]:
            self.assertIn(phrase, joined, phrase)
        for rejection in ["空 token", "占位 token", "父子关系不一致", "文件名不匹配"]:
            self.assertIn(rejection, joined, rejection)
        for field in ['"parent_token"', '"folder":', '"docx":', '"docx_filename"', '"docx_batch"']:
            self.assertIn(field, self.template, field)
        for stale_field in ['"parent":', '"folder_permalink"']:
            self.assertNotIn(stale_field, self.template, stale_field)

    def test_v211_folder_resolution_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in [
            "(parent_token, exact_name)",
            "ensure_feishu_folder",
            "sha256(parent_token + NUL + name)",
            "resolution=reused|created",
            "exact_match_count_first/second/after",
            "pages_scanned_first/second/after",
            "created_token",
            "resolved_at",
        ]:
            self.assertIn(phrase, joined, phrase)
        # helper must not be advertised as deleting/moving/merging duplicates
        for forbidden in ["自动删除", "自动移动", "自动合并", "任选一个"]:
            self.assertNotIn(forbidden, joined, forbidden)

    def test_v210_delivery_mode_contract_and_no_post_qa(self):
        operational = "\n".join([self.skill, self.gate, self.template, self.readme])
        self.assertIn("聊天只发链接", operational)
        self.assertIn("interactive_card", operational)
        self.assertIn("不伪造目录证据", operational)
        for forbidden in ["Post-QA", "审核触发重做", "质量评级", "replacement"]:
            self.assertNotIn(forbidden, operational, forbidden)

    def test_known_template_typos_are_absent(self):
        self.assertNotIn("㮐输出", self.template)
        self.assertNotIn("开实不发出", self.template)


if __name__ == "__main__":
    unittest.main()
