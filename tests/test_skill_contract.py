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

    def test_stale_rules_are_absent(self):
        joined = "\n".join([self.skill, self.gate, self.template])
        self.assertNotIn("逐张做 Post-QA", joined)
        self.assertNotIn("--concurrency 3", joined)


if __name__ == "__main__":
    unittest.main()
