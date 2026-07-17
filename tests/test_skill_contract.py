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
        self.assertRegex(frontmatter, r"(?m)^metadata:\n  version: \"2\.9\.0\"$")

    def test_markdown_fences_are_balanced(self):
        for name in DOCS + ["README.md", "CHANGELOG.md"]:
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(text.count("```") % 2, 0, name)

    def test_version_is_consistent(self):
        for name, text in [("SKILL", self.skill), ("README", self.readme), ("CHANGELOG", self.changelog)]:
            self.assertRegex(text, r"v?2\.9\.0", name)

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

    def test_delivery_modes_and_docx_batch_rule_are_consistent(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in ["--delivery-mode", "docx", "card", "failed_slots", "生成失败"]:
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

    def test_known_template_typos_are_absent(self):
        self.assertNotIn("㮐输出", self.template)
        self.assertNotIn("开实不发出", self.template)


if __name__ == "__main__":
    unittest.main()
