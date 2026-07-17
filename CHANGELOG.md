# Changelog

## v2.12.0

- 新增 `scripts/delivery_config.py` schema v1：`bootstrap`、`status`、`resolve`、`record-success`、`invalidate`，文件锁与原子写入，拒绝凭据字段。
- 默认持久路线为 `docx`；正式路线仅 `docx|interactive_card`，`preview_images` 不构成正式交付。
- manifest 升级 schema v8，`init --delivery-route-file` 消费受控解析证据；移除 `--delivery-mode` 自由选路，v3–v7 用 `init --force` 重建。
- 日常任务直接解析配置，不重复 bootstrap preflight；配置或实际调用失败才诊断。未经用户当前任务明确确认，禁止静默降级；显式覆盖不改持久默认。


## v2.11.0

- 新增 `scripts/ensure_feishu_folder.py`：以 `(parent_token, exact_name)` 为目录身份，在文件锁（锁键 `sha256(parent_token + NUL + name)`）下完整分页列举直属子项；1 个复用、0 个二次查后创建、>1 个阻断；创建后重新列举并验证唯一匹配且 token 等于创建返回 token。
- 新增 `tests/test_ensure_feishu_folder.py`，覆盖复用、创建、并发竞争、分页、分页循环、畳形响应、重复目录、创建后 token 不一致、名称精确匹配、SubprocessJSONAdapter 的 stdout 隔离，以及两进程 spawn 只创建一次的并发合同。
- manifest 升级到 **schema v7**：`delivery.directory_chain[]` 新增 `resolution`、`exact_match_count_first/second/after`、`created`、`created_token`、`pages_scanned_first/second/after`、`resolved_at` 证据；v3–v6 必须 `init --force` 重建。
- `validate --delivery` 新增：`reused` 必须 first=1、`created=false`、`created_token=null`；`created` 必须 first=0/second=0/after=1、`created_token` 与最终 token 一致；任一阶段精确匹配大于 1 阻断；执行阶段 `pages_scanned_*` 必须为正整数；`resolved_at` 必须带时区。
- 重申重复同名目录处置：停止交付、输出候选 token、由用户选定 canonical 目录后再单独迁移清理；helper 不删除、不移动、不合并。
- 保留 v2.10 固定路径与 slug/批次合同、v2.9 无生成后审查合同。

## v2.10.0

- 固定 Listing 路径为 `/{agent_name}/电商需求/Listing/{slug}/`；agent_name 仅取当前工作区 IDENTITY.md 名字字段，目录由 Skill 自动逐层幂等创建。
- 恢复并收紧品牌型号原样 + ISO 大写国家码 slug、空 token/root fallback 防护及 JSON stdout/stderr 隔离合同。
- 图片采用 `MainNNN-NN`、Docx 采用 `YYYYMMDD-{slug}-NNN.docx`，批次独立；返工只推进点名槽位。
- manifest 文档合同升级 schema v6，补充目录链、产品目录、文件名与批次证据及拒绝案例。
- 延续 v2.9 的生成后直接交付规则，不恢复生成后审查、等级判断或由审查触发的重做。

## v2.9.0

- 保留生图前 Pre-QA 分类路由；彻底取消图片生成后的视觉质量审核。
- 删除颜色质量评级、生成后审核报告、瑕疵判断与修改建议。
- 生成成功按图片计划序号直接交付；生成失败按原序号标记“生成失败”。
- manifest 升级到 schema v5，删除根级审核对象、槽位审核标签和审核 mutation；最终验收不再要求审核模式、审核时间或审核槽位记录。
- 交付合同改为 `deliverable_slots` + `failed_slots`：成功槽位校验图片与 token，失败槽位禁止 token。

## v2.8.0

- 图片计划支持 `default_full`、`custom`、`revision` 与动态 `expected_count`；默认完整方案仍为 9 张。
- hard reject 必须补替代槽位；仅用户明确批准时记录短交付 override。
- 非中文完整 Docx 默认目标语言原文逐项紧邻中文对照，严格分离 `source_text`、`zh_reference`、`render_text`。
- manifest schema v4 提供受控 mutation CLI、replacement 谱系、深度 schema 校验、文件锁、保留 mode 的原子替换，以及 manifest_id/generation/revision 冲突防护。
- 精简主 Skill，将质量细节和长模板按条件拆到辅助文件；运行文档移除版本历史叙事。

## v2.7.0 - Full-Pipeline Speedup Without Quality Reduction

**发布日期：** 2026-07-14

### 行为变化

- 5 步业务流程内部重排为 Wave 0 准备、Wave 1 内容、Wave 2 生图交付；独立任务有界并发，同一 Docx 写操作保持有序。
- 新增标准库工具 `scripts/run_manifest.py`，提供 `init`、`timing`、`select-retry`、`validate`，以单一事实源贯穿事实、模块、9 槽位、QA、双 token、状态与耗时。
- 9 张图默认一次提交，`--concurrency 9`；不再以 3 并发起步。
- 部分失败仅按结构化错误码做单槽位重试；成功槽位保留，禁止整批重跑。
- Post-QA 改为九图单轮批审，只有 🔴 候选二次复核；hard reject 与 soft pass 边界保持不变。
- 飞书交付改为流水准备：独立 IM 上传可有界并发，同一 Docx 的 `file_token` 插入按槽位有序；最终统一校验双 token、Docx 和图文卡片。
- `lark-cli` 文档读取改为版本对齐读取 + capability preflight。兼容当前 1.0.68：若 `media-insert --help` 支持 `--selection-with-ellipsis`，即使嵌入 reference 滞后也保留该有效参数。

### 兼容性与质量不变项

- 经与 `origin/main` 的 SKILL 与 CHANGELOG 核对，Variant-Preservation Block 建议化、黄图“≥3 张汇总”规则、ASCII 引号仅手拼命令规避、`--text-file` 不设字符硬阈值，均是 v2.5 self-review 已确定的 canonical SKILL 语义；v2.7 只是统一 QUALITY_GATE 陈旧冲突，不是 v2.7 新降级。

- 保留模块化路由、完整模式门槛、真实性和本地化规则。
- 保留图生图、产品视觉参考图池全传、Pre-QA 分类路由、三段式提示词、默认真人、Post-QA 报告。
- 保留 QA 决策辅助原则：只有明显不是产品图的结果 hard reject，产品可辨认但有瑕疵仍 soft pass。
- 保留飞书 Docx 与图文卡片、每图 `file_token` + `image_key`、latest-per-slot、动态 Docx 章节与聊天框零文案规则。
- manifest 为新增运行时辅助文件；既有 v2.6.2 slug 与历史目录无需迁移。
- 最终 `validate --delivery` 现在硬验收 9 槽位终态、PNG/JPEG/WebP/GIF 真实文件头、九图单轮 QA 审计时间、四段 finite 非负耗时、飞书/Lark HTTPS 链接和格式合理的 token/message_id；card 模式全 token map 禁止 `file_token`，未知槽位与 rejected 槽位 token 均拒绝。

### 验证

- 新增文档契约测试与 manifest CLI 单元测试，统一验证版本、围栏、9 并发、质量红线、增量恢复、hard-reject 边界和交付完整性。
- 标准命令：`python3 -m unittest discover -s tests -v`。

---

# CHANGELOG.md

## v2.6.2 - Slug Edge Cases: Empty Rejection + Whitespace Normalization

### Fixed

- **空品牌型号会生成 `-VN` 残缺目录**：v2.6.1 slug 生成器在用户输入为空、只给品类（"蓝牙耳机"）、或全是禁用字符（`///`）时会退化成 `-VN` 这种以横线开头的目录名，视觉上像 bug，且 shell 命令可能把首字符 `-` 当成 flag 参数解析。
- **换行/制表符在 slug 里保留**：v2.6.1 规则 2 只替换空格，如果用户从表格复制产品名带 `\n` 或 `\t`，slug 里会夹真的换行字符，飞书云盘 / shell / grep 都会踩坑。

### Added

- **§18.4 规则 2（新增前置断言）**：品牌型号短语抽取后必须非空；空则 Agent 打回用户重问"你想上架的具体产品名/型号是什么？"，禁止继续。
- **§18.4 规则 6（新增收尾断言）**：转换完成后主体（去掉国家码）不能为空（即整个 slug 不能以 `-` 开头）；空则同样打回用户。
- **§0 原则 10（新增）**：Slug 边角防呆原则。

### Changed

- **§18.4 规则 3**（原规则 2）：`空格 → 横线` 扩展为 `whitespace（空格/tab/换行/CR）→ 横线`。Python 实现：`re.sub(r"\s+", "-", s)`。
- **§18.4 字符白名单说明**：明确 emoji 属于"其他字符全部保留"范围，跟 v2.6.1 "用户原样" 哲学一致。
- **§18.4 例子表**：加 4 行边角对照（tab、emoji、空品牌、全禁用字符）。
- **QUALITY_GATE §14.1**：加边角断言—— slug 不得以 `-` 开头；不得含原始 whitespace 字符。
- SKILL 版本升级到 2.6.2。README 同步。

### Emoji 决定

Emoji（🎧 / 🌸 / 🔥 等）**保留在 slug 中**。理由：符合 v2.6.1 "用户原样" 核心哲学，如果用户输入了 emoji 那就是产品身份的一部分。飞书云盘文件名支持 UTF-8，不受影响。URL 编码可读性差是分享层的问题，不进 slug 层处理。

### 内部背景

v2.6.1 self-review dry-run 时对抗测试暴露：
- `""` + VN → `-VN`（残缺目录）
- `"///"` + VN → `-VN`（禁用字符删完后主体全空）
- `"B48\nPro"` + VN → `B48\nPro-VN`（换行进 slug）
- `"B48\tPro"` + VN → `B48\tPro-VN`（tab 进 slug）

前两个是"输入不合法"，Agent 应打回用户；后两个是"输入合法但格式不干净"，slug 生成器应归一化。v2.6.2 分开处理这两类。

### 兼容性

**向后兼容**。v2.6.2 只增加规则，不改变 v2.6.1 已合法产出的 slug（v2.6.1 允许生成的 `B48-VN` 之类在 v2.6.2 依然合法）。唯一变化是 v2.6.2 会**主动拒绝**一些 v2.6.1 会被动生成的残缺 slug。

---

## v2.6.1 - Simplified Slug: Product ID + Country Code (User-Preserving)

### Fixed

- **v2.6 slug 规则过度限制**：v2.6 依然沿用 v2.5 的强制小写化 + 白名单过滤 + 变体后缀（如 `b48-nude-den`），实测暴露了三个问题：
  1. **产品身份被破坏**：`B48` 的大写 `B` 是产品身份的一部分，被强制小写化为 `b48` 是自作主张。
  2. **多语言字符被吞**：越南文 `Đen` 会被白名单过滤成 `en`，法文 `é` / 德文 `ü` 类似。
  3. **变体后缀污染 slug**：颜色、市场、语言进 slug 导致同一产品跨市场跨颜色目录爆炸。

### Changed

- **§18.4 Slug 规则**全段重写为极简版：
  - Slug = `{品牌型号原样}-{国家代码}`
  - 品牌型号**完全按用户输入保留**：不小写化、不过滤字符、不加变体后缀
  - 空格 → 横线（唯一强制转换）
  - 只删文件系统禁用字符：`/ \\ : * ? " < > |`
  - 国家代码用 ISO 3166-1 alpha-2 大写（VN / US / TH / BR / JP …）
- **§18.1 目录结构**：产品目录名去掉 `YYYYMMDD-` 前缀。日期只出现在 Docx 文件名。同 slug 跨天复用不影响目录名。
- **§18.3 幂等创建循环**：第 4 层探测名从 `YYYYMMDD-{slug}` 改为 `{slug}`。
- **§0 原则** 追加编号 9：Slug 极简化原则。
- **QUALITY_GATE §14.1** 同步更新路径断言：去掉日期前缀要求。
- **OUTPUT_TEMPLATE §4.1** 交付话术里的目录路径示例同步更新。
- SKILL 版本升级到 2.6.1。README v2.5 段引用同步更新，追加 v2.6.1 段。

### 内部背景

老爸在 v2.6 落地后测试时指出："就不能老老实实 B48，保持用户原生输入的大写 B 吗？"以及"就是说产品名不要给那么多乱七八糟的限制"。核心原则重述：**slug 是产品身份的 anchor，不是产品的完整描述**。变体、语言、颜色由 Docx 内容自己表达；跨市场用国家代码区分。

### 兼容性

**破坏性变更**：v2.5/v2.6 产生的目录（`20260712-b48-nude-den/`）与 v2.6.1 的新目录（`B48-VN/`）不共存复用。老目录保持原状不迁移；新任务在新 slug 路径下建目录。如果需要迁移老 slug 到新格式，用户手动 rename 云盘目录即可（skill 不代理迁移）。

---

## v2.6.0 - Docx Chapters Mirror Output Scope + Feishu Docx for All Complete Deliveries

### Fixed（修两个 v2.5 实战暴露的设计缺陷）

- **Docx 固定 11 章 vs 输出范围可变冲突**：v2.5 §18.7 规定 Docx 必须固定 11 章（§1-§11），但 v2.5 §2.3 完整模式只定义 10 板块文案（不含图片汇总/Post-QA）；完整文案模式下若走 Docx 交付，§10/§11 会成空章，被 QUALITY_GATE §14.4 判定不合格。v2.6 把 Docx 章节列表改为**动态组装**：Docx 内一级章节 = 本次用户实际请求的模块，一一对应。
- **"何时走 Docx" 漏了完整文案模式**：v2.5 §5 步骤 5 只在"生图交付"语境里写了 Docx 分流，导致 Agent 处理"完整文案 + 落飞书" 需求时误走聊天框输出。v2.6 把 Docx 分流规则提级为**通用交付分流**，明确所有完整成品交付（完整文案 / 生图 / 完整=文案+图 / 组合模块完整交付）都走 Docx。

### Added

- **§0 v2.6 新增原则** 两条：
  - 原则 7：Docx 章节 = 输出范围镜像
  - 原则 8：飞书渠道所有完整成品都走 Docx
- **§0 Agent 必须遵守** 追加编号 11、12：明确 Docx 章节列表约束与 Docx 触发条件。
- **§18.0 触发条件（新章节）**：显式列出"必须走 Docx"和"不走 Docx"的场景，覆盖完整文案 / 生图 / 组合模块 / 单模块 / 返工 / 用户显式指示等常见分支。

### Changed

- **§5 步骤 5**：从"分渠道分发"改为"分形态 + 分渠道分流"，新增表格明确「完整成品 vs 非完整成品」和「飞书+认证 / 飞书未认证 / 非飞书渠道」的组合决策。
- **§18 章节标题**：`飞书云文档输出模式（v2.5 新增）` → `飞书云文档交付模式（v2.5 新增；v2.6 扩展至所有完整成品）`。
- **§18.7 Docx 结构**：从固定 11 章表 → 4 形态动态组装表（文案 Docx / 生图 Docx / 全套 Docx / 按需组合 Docx），编号规则改为「Docx 内本地从一起编，不跟随 SKILL.md §1-§11 槽位」。
- **§18.7 阶段 1 markdown 骨架示例**：加注释说明章节按形态动态组装，示例保留为全套 Docx 参考。
- **§18.9 聊天框消息**：改为按形态分支——文案 Docx 只发 Docx + 目录链接；生图 / 全套 Docx 才加 IM 图文卡片行。
- **§8.3 真实产品图生成不合格情况**：追加一条「完整成品在飞书渠道认证下绕过 Docx 直接倒段落」为不合格。
- SKILL 版本升级到 2.6.0。README.md 版本引用从 stale 的 v2.4.0 更新到 v2.6.0，并新增 v2.6 段。

### 内部背景

v2.5 发布后老爸实测「完整上架文案 + 飞书渠道认证已通过」组合时发现 Agent 直接在聊天框倒 10 段文案没有走 Docx。追溯规则冲突：

1. **交付路由缺一层**：v2.5 §5 步骤 5 的 Docx 分流只覆盖生图子流程，没通用化。
2. **Docx 结构死板**：v2.5 §18.7 固定 11 章 + §14.4 空章判不合格 = 完整文案模式下走 Docx 会自动违规。

v2.6 修根子：把 Docx 章节从「结构模板」改为「输出范围镜像」，让 SKILL §2 的模块化路由哲学一直贯穿到 Docx 交付层。

---

## v2.4.0 - Post-Feishu-v0.2 Fixes: Version-Aware Preflight + Multi-Variant Prompt Block + QA Fix Suggestions

### Fixed（修正过时/遗漏）

- **第 16.1 节**删除 "> 8 张自动拆卡" 的错误描述。`feishu-channel-tools >= 0.2.0` 已取消图片张数隐式上限，仅按 25 KiB 字节兜底；旧描述会误导 Agent 写不必要的人工分批逻辑。
- **第 15.1 节**为两个依赖工具标注最低版本：`image-provider-gateway >= 0.2.0`、`feishu-channel-tools >= 0.2.0`。旧本实际依赖新版能力（init 命令、无张数封顶）但未声明。

### Added

- **第 15.2 节 Preflight** 升级为两阶段：先用 `command -v` 判存在，再用 `--version` 断言版本。任一 `MISSING` 或 `NEEDS_UPGRADE` 均需用户授权后重装；不得降级绕行。
- **第 11.2 节**三段式提示词新增可选的 **Variant-Preservation Block**：当本图涉及多个 SKU/颜色变体（多色 flat lay、对比图、套装展示）时强制列举每个变体的颜色 / 位置 / on-body 文字，避免颜色串污或变体数量不对。
- **第 11.2 节**引入“引号降级”硬约束：prompt 字符串禁用 ASCII `"`。需要强调改用中文 `「」`、`“”` 或 ASCII `'`。避免 batch JSON 语法错误。
- **第 14.1 节 Post-QA** 每张 🟡 图必须附**修复方式建议**（重出 / PS 后处理 / 遮盖裁剪 / 直接使用 四选一），让用户一眼看到修复路径。

### Changed

- SKILL 版本升级到 2.4.0。
- QUALITY_GATE.md 第 13.6 不合格列表新增：🟡 图未带修复方式建议 → 不合格。
- QUALITY_GATE.md 第 13.7 硬规则重写：包含两个依赖的最低版本、Preflight 双阶段断言、prompt 双引号禁用、Variant-Preservation Block 必填、`--text-file` 阈值具体化。
- OUTPUT_TEMPLATE.md 交付卡模板的逐张观察例子同步新增"修复建议"字段，包含 logo 错字 → PS，瑕疵 → 重出 等实例。

### 内部背景

本版本尚未重写 v2.3 的 5 步流程与 Agent 多模态自审思路；仅回收 v2.3 发布后实战暴露的 5 个具体瑕疵：

1. 依赖工具 API 已升级，旧描述不再成立
2. Preflight 无版本断言，旧版本工具会静默过卡
3. 多变体图无专用约束，颜色串污多发
4. 中文 prompt 中的 ASCII `"` 多次弄坏 batch JSON
5. Post-QA 报告只列瑕疵没列路径，用户需额外提问

---

## v2.3.0 - Simplified 5-Step Flow + Agent-Native QA + Universal Human Model Default

### Added

- 新增第 6 章“5 步内部执行流程”，替换旧的 8 步。QA 从独立步骤内嵌到步骤 2（审核补齐）和步骤 5（交付）。
- 新增第 11.3 节“参考图池全传”硬规则：产品视觉图池零剔除，不得因主观判断把照片排掉。
- 新增第 11.4 节“真人使用场景默认”：所有类目默认 9 图中 4-6 张含真人，例外必须显式声明。
- 新增第 13 章“Pre-QA 分类路由”：把用户上传图分为产品视觉图 / 信息素材图 / 无关图 三类分别使用。
- 新增第 14 章“Agent 多模态自审”：多模态模型直接看图判定，不再外调 image 子模型。
- 新增第 14.2 节“Hard Reject 边界”：仅剔除“明显不是产品图”（生成失败/损坏/严重跑题/占位图），其余 soft pass 全发。
- 新增第 15.4 节：`image-provider-gateway` 结构化错误码使用指引，包含 12 个 code 与 retryable 建议。
- QUALITY_GATE.md 新增第 13 章“产品图生成质量门槛”五个子节，将 v2.3 新硬规则追加到不合格判定。
- QUALITY_GATE.md 新增产品图生成任务专用的 100 分自检评分维度。
- OUTPUT_TEMPLATE.md 新增第 3 章“真实产品图生成任务输出模板”，包括 5 步对应的 5 个子模板。

### Changed

- SKILL 版本升级到 2.3.0。
- Description 强调内嵌 QA。
- 第 0 章核心原则重写：5 步流程 + Agent 多模态自审 + 参考图分类路由 + 真人默认 + Post-QA 辅助化 六项变更展开。
- 第 5 章“本地化规则”去除对马来西亚/越南的硬编码，改为通用占位符 `{market}` / `{platform}`；不假设具体市场。
- 第 7.4 / 7.10 / 7.11 提示词字段新增“是否包含真人”。
- 第 8.3 不合格判定重写：包含分类路由、全传参考图、默认真人、hard reject 边界、Post-QA 不剔除瑕疵图 五项新硬条。
- 第 12 章 8 步工作流重写为 5 步，内容内嵌到步骤 2 和 5。
- 第 15.3 凭据部分重写：新内容包含 `image-provider-gateway init` 持久化配置流程 + 三层优先级链（CLI > env > 配置文件）。
- 第 16.1 / 16.2 发卡硬规则：长文本正文优先 `--text-file`，避免 heredoc。
- QUALITY_GATE.md 第 8 章 9 图字段新增“是否包含真人”。
- QUALITY_GATE.md 第 15 章失败处理新增 QA 报告不阻塞交付的特殊规则。

### Removed

- 删除旧 8 步工作流中的“外调 image 视觉子模型”描述；QA 全部由 Agent 自己看图完成。
- 删除旧 QA “verdict = reject 时不生图 / 不发图”的卡点逻辑（产品视觉图零剔除 + 生成图默认放行）。
- 删除旧本地化规则中“若目标市场为马来西亚/越南”的硬编码分支。

### Fixed

- 修复以往 QA 卡点导致用户拿不到“有瑕疵但可用”图片的问题。
- 修复默认无真人导致电商图“买家无法想象使用场景”的转化痛点。
- 修复 Agent 主观剔除参考图导致参考信息丢失。
- 修复外调 image 子模型导致的多余开销与一致性风险。

## v2.2.0 - Image-Edit-Only + Integrated Feishu Delivery

### Added

- 新增第 11 章：产品图生成硬规则（Image-Edit-Only），禁止纯文生图。
- 新增第 12 章：产品图生成完整工作流（8 步）：取图 → 前置 QA → 参数确认 → 三段式提示词 → 生图 → 后置 QA → 组装报告 → 飞书发货。
- 新增第 13 章：前置图片 QA，配套 image 视觉模型的 JSON prompt 模板与 pass/conditional/reject 分流。
- 新增第 14 章：后置生成 QA，对比参考图 vs 生成图，输出 pass/needs-revision/reject 判定。
- 新增第 15 章：依赖工具与 preflight 校验，声明 image-provider-gateway 与 feishu-channel-tools 两个外部 CLI 依赖。
- 新增第 16 章：图文交付到飞书，硬规定走 `feishu-tools send-card`，不再依赖 MEDIA 指令。
- 新增 §8.3 缩水判定：真实产品图生成不合格情况。
- 新增第 11.2 节三段式提示词模板：形态锁定块 + 产品外观描述块 + 构图/文字/背景块。

### Changed

- SKILL 版本升级到 2.2.0。
- Description 更新为强调图生图（image edit）+ 前后置 QA + 飞书图文卡片交付。
- 第 6 节内部执行流程新增第 3/7/8 步，覆盖工具 preflight、后置 QA、飞书发货。
- 7.4 9 图提示词规则统一采用三段式模板字段。
- 7.11 SKU 图提示词规则强调必须走图生图。

### Fixed

- 修复以往纯文生图导致产品还原度差的问题。
- 修复图文交付时因 MEDIA 指令被吞而丢图的问题。

## v2.1.0 - Modular Output Router

### Added

- 新增 Modular Output Contract 核心原则。
- 新增 Output Router：按需模式、组合模式、完整模式、返工修订模式。
- 新增未指定输出范围时的模块菜单。
- 新增主图提示词、SKU 图提示词等可独立调用模块。
- 新增按需输出模板。

### Changed

- 默认逻辑从“完整上架模式”改为“按需输出优先”。
- 只有用户明确要求完整上架内容时，才输出固定 10 个板块。
- 质量门槛改为 scope-aware：只检查用户本次请求的模块。
- 返工逻辑改为只重写用户指出的模块，不自动整套重写。
- README 推荐调用语句改为按需、组合、完整三类调用方式。

## v2.0.0 - Output Contract

### Added

- 新增 Output Contract 核心原则。
- 新增完整上架模式，默认固定 10 个输出板块。
- 新增每个板块的最低产出规模。
- 新增内部执行流程：事实提取、卖点池、关键词池、完整输出、自检重写。
- 新增标题关键词模块数量要求。
- 新增核心卖点 8 条硬性要求。
- 新增详情文案 7 个小节硬性要求。
- 新增 9 图提示词字段制模板。
- 新增缩水输出判定规则。
- 新增 100 分质量评分规则。
- 新增 `QUALITY_GATE.md`。
- 新增 `OUTPUT_TEMPLATE.md`。

### Changed

- 将 Skill 从“方向建议型”升级为“交付契约型”。
- 标题规则从“不得过短”升级为“必须满足关键词模块数量”。
- 9 图提示词从“包含若干元素”升级为“每张图固定 10 个字段”。
- 详情文案从“结构建议”升级为“固定小节与最低规模”。
- 关键词从“覆盖类别”升级为“至少 30 个，并按类别分组”。
- 风险提醒从“方向提醒”升级为“3-6 条真实上架风险”。

### Fixed

- 修复 Agent 有时输出过短的问题。
- 修复标题有时像普通产品名而不是电商搜索标题的问题。
- 修复 9 图提示词有时缺少商业文字说明的问题。
- 修复 9 图提示词有时互相引用的问题。
- 修复输入信息较少时整体输出被压缩的问题。

## [2.5.0] - 2026-07-12

### 层级序号规范（round-4，SKILL / OUTPUT_TEMPLATE）

- 新增 SKILL §17.4「输出层级序号规范」：一/二/三…（h2）→（一）/（二）/（三）…（h3）→ 1./2./3.…（h4）→ 1.1/1.2/1.3…（h5）。
- 改 SKILL §18.7 Docx 骨架示例：`§N` 前缀改成中式序号；图片汇总下位置改成 h3「（N）图 N · 用途」；`docs +media-insert --selection-with-ellipsis` 示例用中式序号锚点。
- 改 OUTPUT_TEMPLATE §2 完整上架模式：加层级序号规范小节，引用 SKILL §17.4。
- 目的：统一飞书云文档、长卡片、导出 markdown 等**完整成品**的多级 heading 编号方式，便于人眼扫读与目录展示。


### Self-review 第四轮（空 token 陷阱）

测试中发现的真 bug：当捕获 `lark-cli drive +create-folder --json` 时未重定向 stderr，进度日志 `Creating folder ...` 会污染 JSON 解析失败导致 token 为空；而 lark-cli 官方 CLI 把 `--folder-token ""` **fallback 到根目录**创建目录，造成一发不可收拾的 silent-fail cascade。

同一 PR 里修：
- **§18.3** 目录幂等创建章节新增"空 token 防呆陷阱"专块，明确要求：
  1. 任一步解析 token 后**必须断言非空**；空值 hard fail。
  2. **`--json` 捕获必加 `2>/dev/null`**，隔离进度信息对 stdout 的污染。
  3. **禁止把空值传给下一步 --folder-token**。

### Self-review 第三轮（过度限制清理）

老爸要求“尽可能不要给太多没必要的限制”，实测 CLI 交叉验证后放宽 6 处：

- **§16.1**：删除 "> 500 字符必须用 --text-file" 硬阈值（`feishu-channel-tools` 源码里根本没有 500 这个数），改成"含反引号/$/多行时建议"。
- **§11.2**：prompt 禁 ASCII 双引号 -> 只在"手拼 batch JSON 或 shell 单行"时建议避免；`json.dumps` 生成 JSON 时会自动转义，没有限制必要。
- **§16.4**：静默重试次数从 2 -> 3，对齐 §18.10 已有约定，修内部不一致。
- **§17.3**：Agent 名长度 1-6 字"禁止" -> 1-12 字"建议"，长度本身与飞书 API 无关。
- **§11.2**：Variant-Preservation Block"必须" -> "建议"，实测能减少变体串色但不加也能出图。
- **§14**：🟡 图修复方式建议从"每张必须" -> "≥ 3 张时汇总建议表"，避免 agent 强制生成噪音条目。

### Self-review 第二轮修补（同一 PR 内）

- **🔴 §15.1 / §15.2（阻断修复）**：`image-provider-gateway` 版本要求 `>= 0.2.0` 是幻觉数字（上游只有 0.1.0）；实测本地也是 0.1.0；同时该 CLI **未实现 `--version`**，SKILL 里的 preflight 版本正则 100% 失败。修复：要求降回 `>= 0.1.0`；preflight 版本断言改成 `image-provider-gateway config path >/dev/null` 的 sanity 断言。
- **§12 步骤 5**：过去只写"走 feishu-tools send-card"，现在明确 v2.5 分流：飞书+认证 → §18 Docx；否则 → §16 卡片。
- **§16 头部 / §16.1**：措辞从"必须走 send-card"改为"退回路径下必须走 send-card"，与 §18 主路径区分。
- **§8.3 不合格情况**："绕过第 16 章卡片"改为"绕过 v2.5 分流（§18 / §16）"。
- **§18.5 表格**：Docx 批次 +1 触发条件从"每次跑 Skill"改为"每次实际生成新 Docx"，只发卡片时不 +1。
- **§18.5 例子**：加一句解释"为什么位置 03 是批次 2"（首轮不满意重出）。
- **§18.4 slug 规则**：改写为顺序化 5 步流程；**新增"分隔类符号 → 横线"** 覆盖 `_ + . / \\ , ; |`；加例子表覆盖 6 个 case（含 e2e 验证过的边界）。
- **§18.9 聊天框消息**：措辞去掉"上/下条"歧义，加消息顺序建议（先链接后卡片）。

### Self-review + e2e test 修补（同一 PR 内）
- **§18 头部** 增加 lark-cli 强制约定：进入 docs 操作前 MUST 先跑 `lark-cli skills read lark-doc`（含 create / md / media-insert 三份 references）。
- **§18 头部** 增加"lark-cli `--file` 只接受相对路径"通用陷阱说明。
- **§18.3** 目录 ensure 从纯 raw API 改为"shortcut 优先"：`drive +create-folder` 用于创建，raw `api GET /open-apis/drive/v1/files` 用于列子文件夹。
- **§18.6** 图片双 token 上传从手写 API 改为推荐 shortcut：Docx 走 `docs +media-insert`；IM 走 `im images create --as bot`（必须 bot 身份）。
- **§18.7** Docx 生成流程明确"两阶段"：markdown 一次性 create 骨架（含 h2 占位符）→ 逐张 `+media-insert --selection-with-ellipsis` 精准插入到位置 NN 之后。
- **§18.10** 错误恢复补充 `drive +delete --type docx --yes` 的具体调用姿势，以及 cwd 中间文件清理。
- **§17.3** Agent 名字规范扩充禁用字符列表（`/ \ : | * ? < > "` 全部禁止）。
- **QUALITY_GATE §14.5** 双 token 断言明确 identity 约束（Docx 用 user；IM 用 bot）。

**修补来源：** 本地 e2e 全链路 API 实测（目录 ensure、Docx create、双 token 上传、精准图片插入、清理），确认所有推荐姿势可运行，并暴露了 6 个书面文档不足的问题。测试路径 `/唐予安/电商需求/Listing/20260712-zgar-001-e2e-test/` 及产出物已全部回滚清理。

### Added
- **飞书云文档交付模式**（SKILL §18）：飞书渠道下，产出统一进 Docx 存储到用户飞书云空间。
  - 目录路径：`/{agent_name}/电商需求/Listing/YYYYMMDD-{slug}/`。
  - Agent 名从 `IDENTITY.md` 动态解析（SKILL §17），禁止硬编码。
  - 两套批次计数器：图片逐张独立 +1；Docx 仅在实际生成新文档时 +1，只发卡片时不 +1。
  - Docx 结构固定 §1-§11：10 段文案 + Post-QA 报告。
  - 图片双 token：云盘 `file_token`（永久，Docx 内嵌）+ IM `image_key`（24h，卡片显示）。
- **`lark-cli` 硬依赖**（SKILL §15.1）：`@larksuite/cli >= 1.0.0`，飞书渠道必需。
- **`lark-cli` 认证 preflight**（SKILL §15.2）：检测 user identity ready 状态；`AUTH_MISSING` 时询问用户是否授权，**不设超时**。
- **退回路径**（SKILL §16 头）：`lark-cli` 未认证 + 用户拒绝授权 → 走第 16 章图文卡片。
- **QUALITY_GATE §14**：Docx 目录 / 批次 / 结构 / 双 token / 聊天框零文案的 7 条断言。
- **OUTPUT_TEMPLATE §4**：Docx / 生图卡片 caption / 聊天框消息模板。

### Changed
- **§6 步骤 5** 从"send-card 单路径"改写为按渠道分流的"分渠道分发"（飞书 → §18 Docx / 其他 → §16 卡片）。
- **§16 图文交付到飞书** 定位从"主交付通道"改为"退回路径 / 非 Docx 场景"。
- **frontmatter version**：2.4.0 → 2.5.0。

### Notes
- 生成 slug 由 agent 从用户自然语言中抽品牌+型号后自动生成，用户可改"抽出的短语"但不接受自定义 slug 规则。支持中文 / 英文 / 数字 / 横线。
- Preflight 询问不设超时；用户随时回复继续 / 拒绝退回。

