# CHANGELOG.md

## v2.4.0 - Post-Feishu-v0.2 Fixes: Version-Aware Preflight + Multi-Variant Prompt Block + QA Fix Suggestions

### Fixed（修正过时/遗漏）

- **第 16.1 节**删除 "> 8 张自动拆卡" 的错误描述。`feishu-channel-tools >= 0.2.0` 已取消图片张数隐式上限，仅按 25 KiB 字节兜底；旧描述会误导 Agent 写不必要的人工分批逻辑。
- **第 15.1 节**为两个依赖工具标注最低版本：`image-provider-gateway >= 0.2.0`、`feishu-channel-tools >= 0.2.0`。旧本实际依赖新版能力（init 命令、无张数封顶）但未声明。

### Added

- **第 15.2 节 Preflight** 升级为两阶段：先用 `command -v` 判存在，再用 `--version` 断言版本。任一 `MISSING` 或 `NEEDS_UPGRADE` 均需用户授权后重装；不得降级绕行。
- **第 11.2 节**三段式提示词新增可选的 **Variant-Preservation Block**：当本图涉及多个 SKU/颜色变体（多色 flat lay、对比图、套装展示）时强制列举每个变体的颜色 / 位置 / on-body 文字，避免颜色串污或变体数量不对。
- **第 11.2 节**引入"引号降降"硬约束：prompt 字符串禁用 ASCII `"`。需要强调改用中文 `「」`、`“”` 或 ASCII `'`。避免 batch JSON 语法错误。
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
  - 两套批次计数器：图片逐张独立 +1；Docx 每次跑都 +1。
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

