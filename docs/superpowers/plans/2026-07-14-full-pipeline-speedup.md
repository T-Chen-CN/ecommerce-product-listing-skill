# Full-Pipeline Speedup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不删减任何质量门槛的前提下，将电商 Skill 改造成 9 图满并发、阶段并行、单一事实源、批量 QA、增量重试和流水线式飞书交付的 v2.7.0。

**Architecture:** Skill 仍维持五步业务流程，但内部执行改为三波并行流水线。新增轻量、确定性的运行清单与校验脚本，用一个 manifest 贯穿事实、图片槽位、QA、上传 token 和耗时；所有内容规则仍由 SKILL/QUALITY_GATE/OUTPUT_TEMPLATE 约束。

**Tech Stack:** Markdown AgentSkill、Python 3 标准库、unittest、image-provider-gateway、feishu-tools、lark-cli。

## Global Constraints

- 质量门槛不降低：图生图、参考图池全传、Pre-QA、三段式提示词、默认真人、Post-QA、Docx 与卡片交付全部保留。
- 9 张图默认一次提交，`--concurrency 9`；上游限制为 9 并发。
- 成功图片不得因部分失败而重跑；只对失败槽位按结构化错误码重试。
- 同一 Docx 的写操作保持有序，避免 revision 冲突；独立的 IM 上传、内容生产和准备工作允许有界并发。
- 三份强制规则文件必须一致，不保留互相冲突的旧硬门槛。
- 不直接修改或合并主分支；通过 feature branch 和 PR 交付。

---

### Task 1: 建立契约测试与 v2.7 元数据

**Files:**
- Create: `tests/test_skill_contract.py`
- Modify: `SKILL.md`

**Interfaces:**
- Produces: 可用 `python3 -m unittest discover -s tests -v` 执行的文档契约测试。

- [ ] 写失败测试，覆盖 frontmatter、Markdown 围栏、版本一致性、9 并发、质量红线和禁止的陈旧规则。
- [ ] 运行测试并确认在 v2.6.2 基线上失败。
- [ ] 将版本升级为 v2.7.0，并按当前 AgentSkill frontmatter 规范存放版本元数据。
- [ ] 运行测试，确认元数据与基础契约通过。
- [ ] 提交本任务。

### Task 2: 增加确定性运行清单与校验器

**Files:**
- Create: `scripts/run_manifest.py`
- Create: `tests/test_run_manifest.py`

**Interfaces:**
- Produces: CLI 子命令 `init`、`timing`、`select-retry`、`validate`；manifest 记录事实、模块、图片槽位、QA、token、阶段耗时与状态。

- [ ] 写失败测试，覆盖 9 个槽位初始化、耗时记录、仅失败槽位重试、hard-reject 边界和交付完整性。
- [ ] 实现仅依赖 Python 标准库的最小 CLI。
- [ ] 验证测试全部通过，且脚本 `--help` 可运行。
- [ ] 提交本任务。

### Task 3: 将五步流程重构为三波并行流水线

**Files:**
- Modify: `SKILL.md`
- Modify: `QUALITY_GATE.md`
- Modify: `OUTPUT_TEMPLATE.md`

**Interfaces:**
- Consumes: `scripts/run_manifest.py` 的运行清单。
- Produces: Wave 0 准备、Wave 1 内容、Wave 2 生图交付的明确依赖图与命令范式。

- [ ] 在 SKILL 中定义单一事实源、合并确认关口和阶段计时。
- [ ] 把 9 图生图改为 `--concurrency 9`，明确单槽位重试和禁止整批重跑。
- [ ] 定义并行边界：独立读取/内容模块/IM 上传可并发；同一 Docx 写操作有序执行。
- [ ] 将 Post-QA 改为九图单轮批审，只有 🔴 候选二次复核；保持 hard/soft pass 边界。
- [ ] 将飞书交付改成上传与文档准备流水化，并保留双 token 和最终统一验收。
- [ ] 同步 QUALITY_GATE 与 OUTPUT_TEMPLATE，修复围栏和所有陈旧冲突。
- [ ] 运行契约测试并提交本任务。

### Task 4: 文档、变更记录与全量验证

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: v2.7.0 用户说明、性能设计说明和可复现验证证据。

- [ ] 更新 README，说明提速来自并行、流水线、单一事实源和增量恢复，而非质量缩水。
- [ ] 更新 CHANGELOG，逐项记录兼容性和行为变化。
- [ ] 运行 unittest、quick_validate、Markdown 围栏检查、全仓关键词漂移检查。
- [ ] 检查 git diff，确保无意外标点或范围外改动。
- [ ] 提交最终文档任务。

### Task 5: 独立复核与 PR

**Files:**
- Review: branch full diff

**Interfaces:**
- Produces: 独立代码审查结论与 GitHub PR。

- [ ] 对完整分支做规格符合性和质量复核。
- [ ] 修复所有 Critical/Important 问题并重新验证。
- [ ] 推送 `perf/full-pipeline-speedup`。
- [ ] 创建 PR，正文包含方案、质量不变项、测试证据和已知边界。
