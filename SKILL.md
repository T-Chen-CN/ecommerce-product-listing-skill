---
name: ecommerce-product-listing-skill
description: "Use when producing or revising localized ecommerce listing copy, product-image plans, generated product images, or Feishu delivery artifacts."
metadata:
  version: "2.8.0"
---

# 跨境电商上架内容生产

## 核心原则

按用户本次要求生产可直接上架的文案、图片或交付物，不擅自扩大范围。事实真实性高于营销完整度；未知参数标记“未提供 / 需确认”，不得猜测。

## 按任务条件读取

不要一律加载全部辅助文件：

- 需要模块格式、Docx 骨架或卡片正文时读 `OUTPUT_TEMPLATE.md`。
- 进入最终自检、真实生图或飞书交付时读 `QUALITY_GATE.md`。
- 需要飞书具体命令时先读已安装 `lark-doc` Skill 及其对应 reference，并以当前 CLI `--help` 为准。
- 版本变更历史只查 `CHANGELOG.md`；它不参与运行判断。

## 1. 请求路由

先确定用户要求的模块；返工只修改点名模块。真实产品图任务再确定图片计划：

- **default_full**：用户仅给产品信息并泛化要求“做产品图”，采用默认完整方案 9 张，`expected_count=9`。
- **custom**：用户提到 SKU 图、特定卖点图、指定图型或其他明确图片范围，按明确数量执行。
- **revision**：返工指定槽位，只处理明确槽位。
- custom/revision 数量不明确时，必须先给出“槽位清单 + 总数”并只做一次合并确认；确认前不生图。确认结果记为 `confirmed_by_user=true`。

默认完整方案 9 张不是所有任务的固定数。最终验收为 default_full `9/9`，custom/revision `N/N`。

## 2. 事实与本地化

信息优先级：用户参数表 > 用户确认内容 > 图片中清晰可见事实 > 市场惯例。市场与平台不明确且会影响产出时合并询问一次。

非中文目标市场的完整 Docx 默认使用“目标语言原文 + 逐项紧邻中文对照”，方便运营审核；用户显式要求单语可关闭。中文市场不重复中文。

manifest 明确记录 `localization_policy`、`target_language` 与 `docx_language_mode=bilingual|target_only|chinese`。显式语言优先；未给语言时由 market 判断是否中文市场，其他市场通用默认 bilingual，不靠国家白名单枚举非中文市场。`--monolingual` 必须带用户确认文本；中文市场使用 chinese，不重复。

所有被请求内容模块用三字段表达：

```json
{"source_text":"目标语言原文","zh_reference":"紧邻的中文对照","render_text":"实际用于目标市场或图片的文字"}
```

- 完整 Docx 所属模块必须在 `init --requested-module <name>` 阶段按用户本次请求预声明；`module_contracts.<name>` 为 `docx_text` 字符串。内部状态与非文本数据分别用 internal/non_text，不参与双语正文验收。
- `source_text`：目标语言内容原文。
- `zh_reference`：仅用于 Docx 对照，不进入消费者素材。
- `render_text`：实际发布或图片渲染文字，只允许目标市场语言。
- 中文对照不得传入生图 prompt；prompt 只能消费 `render_text`，不得拼接 `zh_reference`。

## 3. 单一事实源与受控写入

先声明 `task_scope=content|image|full`。content 纯文案/单模块 Docx 使用 `expected_count=0`，不创建图片合同；image/full 才创建动态图片合同。

创建 manifest：

```bash
python3 scripts/run_manifest.py init run-manifest.json --task-scope content --target-language fr --delivery-mode docx
python3 scripts/run_manifest.py init run-manifest.json --task-scope image --plan-mode default_full --delivery-mode docx
python3 scripts/run_manifest.py init run-manifest.json --plan-mode custom --expected-count N --confirmed-by-user
python3 scripts/run_manifest.py init run-manifest.json --plan-mode revision --expected-count N --confirmed-by-user
```

manifest 是单一事实源，包含 `schema_version`、`manifest_id`、`generation`、`revision`、固定 `run_root`、`plan_mode`、`expected_count`、动态 `images`、事实、模块、QA、token、交付证据和耗时。先读取 manifest（即 snapshot）取得完整 identity；子任务不得手改 JSON，必须使用受控 CLI：

```text
set-facts / set-image-plan / add-replacement-slot / put-module（`--module-kind docx_text|internal|non_text`） / update-slot / set-qa /
set-token / set-delivery / timing / finalize / validate / select-retry
```

旧 `schema v3` 运行清单不能直接 mutation/validate，必须执行 `init --force` 安全重建为 v4；CLI 只读取并验证旧 generation/revision 的最低类型要求，保留代际单调并生成新 identity。

并发写由文件锁串行化，保存使用同目录临时文件 + 原子替换并保留原文件 mode。manifest 用 `manifest_id` + `generation` 防 force ABA，`revision` 单调递增；所有覆盖型 mutation 必须同时传读取时的 `--revision`、`--manifest-id`、`--generation`（三个参数 all-or-none），任一不一致都冲突失败。仅 `put-module` / `timing` 这种原子 field-specific append 可显式用 `--from-current`；同字段竞争仍禁止盲写。替代图仅在合同槽 hard reject 后用 `add-replacement-slot --replaces-slot N` 创建并记录 `attempt` + `predecessor_slot` 顺序谱系；一个合同槽只允许一个 active final replacement，禁止手改 JSON。图片路径 resolve 后必须在 init 固化的 `run_root` 内，拒绝外部绝对路径、`..` 与 symlink 逃逸。

## 4. 三波执行

### Wave 0：准备

- 对用户图片做 Pre-QA 分类：产品视觉图 / 信息素材图 / 无关图。
- 产品视觉参考图池零主观剔除；真实生图时参考图池全传。超过工具硬上限才可技术截断并告知。
- 做工具存在性、认证、版本对齐和 capability preflight。
- 在合并确认关口一次确认事实、模块、图片槽位清单与总数。

### Wave 1：内容

独立模块可有界并发，但只消费 manifest 已确认事实，并用 CLI 合并。图片 prompt 使用三段式：形态锁定 + 产品外观 + 构图/文字/背景；多 SKU 可加 Variant-Preservation Block，不作硬门槛。默认真人使用场景，除非用户要求无模特、触发安全限制或产品不适用。

用 `json.dumps` 生成 JSON 时 ASCII 双引号会自动转义；只有手拼 batch JSON 或 shell 单行时才需额外处理。长文本可用文件输入，不设硬字符阈值。

### Wave 2：生图、QA 与交付

- 产品图默认图生图：`--mode edit` + 产品视觉参考图池全传。只有用户明确批准文生图才例外。
- 并发数按实际 N 和工具上限设置，不机械固定 9；成功槽位复用，失败只做单槽位重试，禁止整批重跑。
- 首轮结果做同一上下文 single-round 批审；默认 9 张时即九图单轮批审。🟢/🟡 一轮定稿，只有 🔴 候选再复核。
- hard reject 仅限 API/文件损坏、严重跑题、安全占位、完全不可辨认；产品可辨认但有瑕疵属于 soft pass。🟡 图 ≥ 3 张时提供汇总建议表。
- hard reject 不能自动减少约定数量：必须补齐替代槽位。短交付必须先用 `set-short-delivery-approval --provider ... --channel ... --message-id ... --author-id ... --approval-text '用户批准当前 N->M 合同的原文或规范化明确批准内容' --captured-at <带时区时间> --approved-count M` 记录审批证据。CLI 将 expected/actual、manifest identity/generation、author/provider/channel/message_id、captured_at 和批准内容计算 evidence digest，并把完整 evidence/digest 绑定进 finalize hash；字段被改动后校验失败。审批文本按数字边界精确匹配当前 N->M（例如 19->0 不接受 9->0）。CLI 录入时还原子登记本地唯一消费 registry，以 `(provider, channel, message_id)` 为 key；默认位于稳定的 XDG state 路径，可用 `RUN_MANIFEST_APPROVAL_REGISTRY` 或 `--approval-registry` 隔离测试。registry 与本地 hash 只提供本机防重放/防篡改绑定，不证明外部消息真实性或用户身份；来源真实性必须由渠道读取结果或可信调用方验证。

## 5. 交付路由

- 飞书渠道的完整成品，在 `lark-cli` 已认证且 capability preflight 通过时默认走 Docx；聊天框只发链接。单模块小交付、指定返工或用户要求直接聊天时可不建 Docx。
- Docx 模式：可交付图片需 `file_token` + `image_key`，并保留 Docx、目录和卡片证据。
- card 模式：只发卡片；需 `image_key` 和卡片证据，禁止残留 `file_token`、Docx 或目录证据。
- 同一 Docx 写操作有序；不同 Docx 和独立 IM 上传可有界并发。
- 飞书写入前必须做版本对齐与 capability preflight；当前 `media-insert --help` 支持 `--selection-with-ellipsis` 时保留该参数。

## 6. 最终验收

运行：

```bash
python3 scripts/run_manifest.py validate run-manifest.json --delivery
```

验收要求：

- content scope 为 0 图，只验收内容 Docx 与目录证据，不要求图片、QA、token 或卡片；image/full 的 default_full 为 9/9，custom/revision 为 N/N。
- 每槽位 success 或合法 rejected；若存在 rejected，已有替代槽位补足 N/N，或存在通过 `set-short-delivery-approval` 预先记录并绑定当前 N→M 合同的结构化审批证据。
- success 文件具有 PNG/JPEG/WebP/GIF 文件头。
- QA 留 `N-image-single-round`（默认 9 兼容 `nine-image-single-round`）和 ISO `reviewed_at`。
- `wave_0`、`wave_1`、`wave_2`、`total` 有限且非负，total 不小于任一单波。
- `deliverable_slots`、`rejected_slots`、token 与所选交付模式一致。

任何验收失败都只修复受影响模块或槽位，不降低约定数量，不隐藏错误。
