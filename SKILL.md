---
name: ecommerce-product-listing-skill
description: "Use when producing or revising localized ecommerce listing copy, product-image plans, generated product images, or Feishu delivery artifacts."
metadata:
  version: "2.12.0"
---

# 跨境电商上架内容生产

## 核心原则

按用户本次要求生产可直接上架的文案、图片或交付物，不擅自扩大范围。事实真实性高于营销完整度；未知参数标记“未提供 / 需确认”，不得猜测。

图片流程只保留生图前的 Pre-QA。生成后不做视觉质量审核、不判断产品还原度、文字准确性或画面瑕疵，也不输出质量分级与修改建议。生成成功按序号直接交付；生成失败按对应序号如实标记“生成失败”。

## 按任务条件读取

- 需要模块格式、Docx 骨架或卡片正文时读 `OUTPUT_TEMPLATE.md`。
- 进入最终自检、真实生图或飞书交付时读 `QUALITY_GATE.md`。
- 需要飞书具体命令时先读已安装 `lark-doc` Skill 及对应 reference，并以当前 CLI `--help` 为准。
- 版本历史只查 `CHANGELOG.md`；它不参与运行判断。

## 1. 请求路由

先确定用户要求的模块；返工只修改点名模块。真实产品图任务再确定图片计划：

- **default_full**：泛化要求“做产品图”时，采用默认完整方案 9 张，`expected_count=9`。
- **custom**：SKU 图、特定卖点图、指定图型等按明确数量执行。
- **revision**：只处理明确返工槽位。
- custom/revision 数量不明确时，先给出“槽位清单 + 总数”并只做一次合并确认；确认前不生图。

默认完整方案 9 张不是所有任务的固定数。每个约定槽位最终为 `success` 或 `failed`，不得隐藏失败。

## 2. 事实与本地化

信息优先级：用户参数表 > 用户确认内容 > 图片中清晰可见事实 > 市场惯例。市场与平台不明确且会影响产出时合并询问一次。

非中文目标市场的完整 Docx 默认使用“目标语言原文 + 逐项紧邻中文对照”；用户显式要求单语可关闭。中文市场不重复中文。

manifest 记录 `localization_policy`、`target_language` 与 `docx_language_mode=bilingual|target_only|chinese`。显式语言优先；`--monolingual` 必须带用户确认文本。

所有被请求内容模块使用：

```json
{"source_text":"目标语言原文","zh_reference":"紧邻的中文对照","render_text":"实际用于目标市场或图片的文字"}
```

- Docx 模块须在 `init --requested-module <name>` 阶段预声明为 `docx_text`。
- `zh_reference` 仅用于 Docx 对照，不得进入消费者素材或生图 prompt。
- prompt 只能消费 `render_text`。

## 3. 单一事实源与受控写入

先声明 `task_scope=content|image|full`。content 使用 `expected_count=0`；image/full 创建动态图片合同。

```bash
python3 scripts/run_manifest.py init run-manifest.json --task-scope content --target-language fr --delivery-route-file route.json
python3 scripts/run_manifest.py init run-manifest.json --task-scope image --plan-mode default_full --delivery-route-file route.json
python3 scripts/run_manifest.py init run-manifest.json --plan-mode custom --expected-count N --confirmed-by-user
python3 scripts/run_manifest.py init run-manifest.json --plan-mode revision --expected-count N --confirmed-by-user
```

manifest 是单一事实源，包含 identity、固定 `run_root`、计划、动态 `images`、事实、模块、token、交付证据和耗时；不包含生成后审核字段。子任务不得手改 JSON，只能使用受控 CLI：

```text
set-facts / set-image-plan / put-module / update-slot / set-token /
set-delivery / timing / finalize / validate / select-retry
```

旧 schema 运行清单不能直接 mutation/validate，必须执行 `init --force` 重建为当前 schema。并发写由文件锁串行化并原子保存。覆盖型 mutation 必须携带同一 snapshot 的 `--revision`、`--manifest-id`、`--generation`；图片路径必须位于固化的 `run_root` 内。

## 4. 三波执行

### Wave 0：准备

- 对用户图片做 Pre-QA 分类：产品视觉图 / 信息素材图 / 无关图。
- 产品视觉参考图池零主观剔除并全传；超过工具硬上限才可技术截断并告知。
- 做工具存在性、认证、版本对齐和 capability preflight。
- 在合并确认关口一次确认事实、模块、图片槽位清单与总数。

### Wave 1：内容

独立模块可有界并发，但只消费 manifest 已确认事实。图片 prompt 使用三段式：形态锁定 + 产品外观 + 构图/文字/背景；多 SKU 可加 Variant-Preservation Block，不作硬门槛。默认真人使用场景，除非用户要求无模特、触发安全限制或产品不适用。

用 `json.dumps` 生成 JSON 时 ASCII 双引号会自动转义；只有手拼 batch JSON 或 shell 单行时才需额外处理。长文本可用文件输入，不设硬字符阈值。

### Wave 2：图片生成与交付

- 产品图默认图生图：`--mode edit` + 产品视觉参考图池全传。只有用户明确批准文生图才例外。
- 并发数按实际 N 和工具上限设置；成功槽位复用。结构化可重试错误只做单槽位重试，禁止整批重跑。
- 重试结束后，`success` 槽位按图片计划序号直接交付，不做生成后视觉审查。
- `failed` 槽位按原序号标记“生成失败”，保留 provider 错误事实，不做分析、不触发质量补图或重做。
- 不输出颜色等级、生成后审核报告或修改建议。

## 5. 持久化飞书交付路由

- `scripts/delivery_config.py` 维护无凭据 schema v1 配置，命令为 `bootstrap`、`status`、`resolve`、`record-success`、`invalidate`。默认正式路线是 `docx`；另一正式路线是 `interactive_card`；`preview_images` 只用于用户明确要求的散图预览，不是正式路线。
- 首次安装，或配置缺失、配置损坏、版本不兼容、已失效时，才做 lark-cli 身份、Docx/云盘/插图能力和最小调用检查，再用 `bootstrap` 保存非敏感结果。运行时不得重复全量 preflight。
- 正常任务直接 `resolve`，把输出保存为 route JSON，再用 `init --delivery-route-file route.json`。来源只能是 `skill_config`、`bootstrap_result` 或 `explicit_user_override`。
- 实际调用失败时先诊断：临时错误有限重试原路线；认证/权限错误停止并重新授权；配置错误重新 bootstrap。Docx 不可用时，只有用户针对本次任务明确确认，才可用 `explicit_user_override` 临时改为 `interactive_card`；禁止静默降级，且不修改持久默认值。
- `docx`：成功图片需 `file_token` + `image_key`，聊天只发链接。`interactive_card`：成功图片需 `image_key`，禁止残留 Docx/目录证据。失败槽位均按序号写“生成失败”。
- 成功后调用 `record-success`；认证、权限或资源失效时调用 `invalidate`。同一 Docx 写操作有序；不同 Docx 和独立 IM 上传可有界并发。

## 6. 最终验收

```bash
python3 scripts/run_manifest.py validate run-manifest.json --delivery
```

- content scope 只验内容 Docx 与目录证据。
- image/full 的每个约定槽位必须是 `success` 或 `failed`；成功与失败数量合计为 `expected_count`。
- `success` 文件须有 PNG/JPEG/WebP/GIF 文件头，并具备对应交付 token。
- `failed` 必须有生成失败事实，不得拥有交付 token。
- `wave_0`、`wave_1`、`wave_2`、`total` 有限且非负，total 不小于任一单波。
- `deliverable_slots`、`failed_slots`、token 与所选交付模式一致。

验收失败时只修复结构、文件或交付证据；不得添加生成后质量判断，也不得隐藏生成失败。


## 7. 飞书 Listing 目录合同

固定交付路径为 `/{agent_name}/电商需求/Listing/{slug}/`。

### 7.1 Agent 名与目录创建

- `agent_name` 只能从当前工作区 `IDENTITY.md` 的“名字”字段读取；字段缺失、空白或解析失败必须 **hard fail**。禁止用 `open_id`、`agent id` 或任何运行时标识兜底。
- Skill 自动从根目录开始逐层解析 `{agent_name}`、`电商需求`、`Listing`、`{slug}`。每一层的逻辑身份为 `(parent_token, exact_name)`，不得以名字单独或全盘搜索命中作为身份。
- 每层解析必须调用 `scripts/ensure_feishu_folder.py` 或等价 helper，进入单机跨进程文件锁（锁键 `sha256(parent_token + NUL + name)`），并遵守：
  - 完整分页列出该父目录直属子项，直到 `has_more=false`，不得用全盘搜索代替；
  - 只匹配 `type=folder` 且 `name` 字节级精确相等；
  - **1 个** 精确匹配：复用其 token，禁止调用创建接口；
  - **0 个**：锁内再做一次完整列举；仍为 0 才允许创建；阶段发现 1 个则直接复用；
  - **>1 个** 出现在任一阶段：立即阻断，携带候选证据，禁止任选、删除、移动或合并；
  - 创建后重新完整列举，必须恰好 1 个精确匹配，且其 token 等于创建接口返回 token，否则阻断。
- 文件锁只保证同一 OpenClaw 主机内互斥；跨主机或外部并发由“创建后复核”兜底，不声称绝对防抖。
- 每层解析结果都须验证名称、`type=folder` 与父子关系；创建后立即回读并做同样验证。不得仅凭 token 存在或命令零退出就继续。

### 7.2 Slug

`slug={品牌型号原样规范化}-{ISO 3166-1 alpha-2 大写国家码}`。

1. 主体只取用户给出的品牌型号原样，不改大小写、不音译。
2. 所有 whitespace（空格、tab、换行、CR）替换为横线；连续横线折叠为一个，并从两端剥离。
3. 删除文件系统禁用字符 `/ \ : * ? " < > |`，再执行一次横线折叠与剥离。
4. 规范化前后的主体都必须非空；为空时追问“你想上架的具体产品名/型号是什么？”，不得生成仅含国家码的 slug。
5. 颜色、语言、包装、SKU、retry、revision、日期均不进入 slug。SKU 仅在用户明说时用于图片资产名。
6. 同产品同市场跨天、retry 与返工继续复用同一产品目录。

### 7.3 防空 token 与 JSON 捕获

- 每层 token、根 token 与 `product_folder_token` 均须为非空且不是 `null`、`none`、`undefined`、`TODO`、`<token>` 等占位值；禁止静默 root fallback。
- CLI 的 JSON 捕获必须隔离 stderr：stdout 只接收并解析 JSON，stderr 单独保存或直通诊断。非 JSON、空输出、命令非零退出均 hard fail。

## 8. 资产、批次与目录证据

- 普通图片资产名使用 `MainNNN-NN`；SKU仅在用户明说时使用 SKU 前缀。`NNN` 是该槽位图片批次，`NN` 是槽位号。
- Docx 文件名为 `YYYYMMDD-{slug}-NNN.docx`。Docx 批次与图片批次是独立批次，分别递增，不互相推导。
- 返工只修改点名槽位批次，其他槽位批次与成功资产保持不变。
- latest-per-slot 的唯一含义是：**新文档按每槽位当前最新成功资产**组装；某槽位没有成功资产时写“生成失败”。不建立替代谱系。

manifest 目录证据采用 **schema v8**。字段至少包括：`agent_name`、`product_slug`、`market_country_code`、`drive_path_segments`、`delivery.directory_chain`、`delivery.product_folder_token`、`delivery.folder.permalink`、`delivery.docx.docx_filename`、`delivery.docx.docx_batch`；每个图片槽位记录 `images[].asset_filename` 与 `images[].image_batch`。schema v3–v7 运行清单必须 `init --force` 重建为 v8。

`delivery.directory_chain[]` 每层需携带目录解析证据：`name`、`type`、`token`、`parent_token`、`resolution=reused|created`、`exact_match_count_first/second/after`、`created`、`created_token`、`pages_scanned_first/second/after`、`resolved_at`（带时区）。

`validate --delivery` 必须拒绝：空 token、占位 token、目录名称/type/父子关系不一致、路径段不等于固定路径、产品目录 token 或 folder permalink 缺失、Docx/图片文件名不匹配、批次非正整数、国家码非 ISO 大写格式；`resolution` 缺失或非 `reused|created`；`reused` 时首次匹配数不为 1、`created=true` 或 `created_token` 非空；`created` 时三阶段计数不满足 0/0/1、`created_token` 与最终 token 不一致；任一阶段精确匹配数大于 1；执行阶段的 `pages_scanned_*` 不是正整数。interactive_card 模式不伪造目录证据；未创建 Docx/目录时对应字段必须为空且不得声称已完成目录交付。

manifest 只证明本次受控流程内部自洽，不证明飞书远端当前绝对真实。同一父目录出现多个精确同名目录时必须停止交付，输出候选 token，由用户显式选定 canonical 目录后再单独迁移清理。
