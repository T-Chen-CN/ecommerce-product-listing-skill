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
        self.assertRegex(frontmatter, r'(?m)^description: ".*v2\.7\.0.*"$')
        self.assertNotRegex(frontmatter, r"(?m)^version:")
        self.assertRegex(frontmatter, r"(?m)^metadata:\n  version: \"2\.7\.0\"$")

    def test_markdown_fences_are_balanced(self):
        for name in DOCS + ["README.md", "CHANGELOG.md"]:
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(text.count("```") % 2, 0, name)

    def test_version_is_consistent(self):
        for name, text in [("SKILL", self.skill), ("README", self.readme), ("CHANGELOG", self.changelog)]:
            self.assertIn("v2.7.0", text, name)

    def test_nine_image_default_is_full_concurrency(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        self.assertGreaterEqual(joined.count("--concurrency 9"), 3)
        self.assertNotIn("--concurrency 3", joined)
        self.assertIn("9 张图默认一次提交", joined)

    def test_quality_red_lines_remain(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        required = [
            "图生图", "参考图池全传", "Pre-QA", "三段式", "默认真人",
            "Post-QA", "Docx", "图文卡片", "file_token", "image_key",
            "hard reject", "soft pass",
        ]
        for phrase in required:
            self.assertIn(phrase, joined, phrase)

    def test_pipeline_and_incremental_recovery_contract(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        for phrase in ["Wave 0", "Wave 1", "Wave 2", "单一事实源", "合并确认关口", "单槽位重试", "禁止整批重跑", "九图单轮批审", "同一 Docx 写操作有序"]:
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
        self.assertIn("🟡 图 ≥ 3 张时", joined)
        self.assertIn("汇总建议表", joined)
        self.assertNotIn("🟡 图未带\"修复方式建议\"字段", joined)
        self.assertNotIn("逐张做 Post-QA", joined)
        self.assertNotIn("--concurrency 3", joined)

    def test_v27_preserves_origin_main_v25_canonical_relaxations(self):
        joined = "\n".join([self.skill, self.gate, self.readme, self.changelog])
        for phrase in [
            "v2.5 self-review", "canonical SKILL", "不是 v2.7 新降级",
            "Variant-Preservation Block", "不作硬门槛", "不设硬字符阈值",
            "ASCII 双引号会自动转义", "🟡 图 ≥ 3 张时",
        ]:
            self.assertIn(phrase, joined, phrase)

    def test_manifest_final_acceptance_evidence_is_documented(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in [
            "nine-image-single-round", "reviewed_at", "wave_0", "wave_1", "wave_2",
            "total", "PNG/JPEG/WebP/GIF", "success 或合法 rejected",
        ]:
            self.assertIn(phrase, joined, phrase)
        self.assertNotIn("详见 SKILL §5 步骤 5", self.gate)

    def test_delivery_modes_and_docx_batch_rule_are_consistent(self):
        joined = "\n".join([self.skill, self.gate, self.template, self.readme])
        for phrase in ["--delivery-mode", "docx", "card", "只发卡片", "hard-rejected"]:
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

    def test_readme_marks_v25_as_superseded_history(self):
        section = self.readme.split("## v2.5", 1)[1].split("## v2.6", 1)[0]
        self.assertIn("历史说明", section)
        self.assertIn("已被 v2.6+", section)
        self.assertIn("不再声称“所有产出统一 Docx”", section)
        self.assertIn("不要求固定 11 章", section)

    def test_known_template_typos_are_absent(self):
        self.assertNotIn("㮐输出", self.template)
        self.assertNotIn("开实不发出", self.template)


if __name__ == "__main__":
    unittest.main()
