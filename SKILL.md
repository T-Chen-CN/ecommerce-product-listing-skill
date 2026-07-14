---
name: ecommerce-product-listing-skill
description: "跨境电商上架内容模块化生产、图生图产品图、内嵌 QA 与飞书云文档交付（v2.7.0）。"
metadata:
  version: "2.7.0"
---

# 跨境电商产品上架与本地化内容生产 Skill

## 0. v2.3 核心原则：Modular Output + 5-Step Flow + Agent-Native QA

本 Skill 是一个【模块化电商上架内容交付契约】，不是一次性固定全量输出工具。

默认原则：用户本次要什么，就只输出什么。

只有当用户明确要求"完整上架内容 / 全部内容 / 整套资料 / 全量输出 / 完整上架模式"时，才进入【完整上架模式】。

v2.3 在 v2.2 基础上做了 6 项优化，一切规则保持类目/市场/平台/语言中立：

1. **5 步工作流**：把旧 8 步中的独立 QA 环节内嵌到"审核补齐"和"交付"里。
2. **Agent 多模态自审**：Agent 本身是多模态模型，直接看图判定；不再外调 `image` 视觉子模型。
3. **Pre-QA 是分类路由不是剔除**：把用户上传图分为「产品视觉图 / 信息素材图 / 无关图」三类分别使用；产品视觉图池"零剔除"全部作为生图参考。
4. **真人使用场景为通用默认**：所有类目的产品图默认包含真人使用/穿着/持握/操作场景，让买家想象自己在用；除非用户显式指令、被过滤器拦截、或产品无法体现"使用"。
5. **Post-QA 只剔除"明显不是产品图"**：生成图有瑕疵但产品可辨认必须发；只有生成失败/严重跑题/损坏/占位图才 hard reject。
6. **QA 是决策辅助不是卡点**：Post-QA 报告作为信息附录附在交付里，不阻塞发货，不代替用户判断。

### v2.6 新增（在 v2.5 基础上）

v2.6 修两个 v2.5 实战暴露的设计缺陷，其他规则完全兼容：

7. **Docx 章节 = 输出范围镜像**：Docx 内一级章节列表必须与本次用户实际请求的模块一致，不再固定 11 章。四种典型形态（文案 Docx / 生图 Docx / 全套 Docx / 按需组合 Docx）见 §18.7。
8. **飞书渠道所有完整成品都走 Docx**：飞书渠道 + `lark-cli` 已认证时，任何完整成品交付（完整文案 / 生图完成 / 完整=文案+图 / 组合模块完整交付）默认走 §18 Docx，聊天框只发链接。单模块小交付、返工修订、用户显式指示"直接聊天框"除外。见 §5 步骤 5 与 §18.0。
9. **Slug 极简化（v2.6.1）**：产品目录 slug = 用户原样品牌/型号短语 + 国家代码（ISO 3166-1 alpha-2 大写），不对产品名做大小写变换、白名单过滤或变体后缀。目录名不再带 `YYYYMMDD-` 前缀，日期只出现在 Docx 文件名里。详见 §18.1、§18.4。
10. **Slug 边角防呆（v2.6.2）**：空品牌型号 / 主体全被删空的 slug **必须打回用户重问**，禁止生成 `-{国家码}` 残缺目录；whitespace（空格 / tab / 换行 / CR）统一转横线。详见 §18.4。

### v2.7 新增：三波并行流水线

11. **单一事实源**：每次运行先用 `scripts/run_manifest.py init` 建立 manifest；事实、模块、9 个图片槽位、QA、双 token、状态和阶段耗时只在该清单合并，禁止靠多份临时笔记互相覆盖。
12. **三波并行**：Wave 0 准备、Wave 1 内容、Wave 2 生图与交付。独立读取、内容模块、IM 上传可有界并发；同一 Docx 写操作有序执行。
13. **9 图满并发与增量恢复**：9 张图默认一次提交，`--concurrency 9`；成功槽位绝不因部分失败重跑，只按结构化错误码执行单槽位重试，禁止整批重跑。
14. **批量 QA 与流水交付**：Post-QA 先做九图单轮批审，只有 🔴 候选二次复核；上传、Docx 准备和卡片准备流水化，最终以双 token 和统一验收收口。

Agent 必须遵守：

1. 输出范围由用户本次请求决定，不得默认全量输出。
2. 用户只要求某个模块时，只输出该模块。
3. 用户要求多个模块时，只输出用户点名的模块。
4. 用户明确要求完整上架内容时，才输出完整 10 个板块。
5. 每个模块都必须能独立运行，并保持该模块的最低质量门槛。
6. 真实信息优先，所有参数、颜色、规格、包装以用户提供或明确确认的信息为准。
7. 信息不足时，不得编写不存在的信息；必要位置写"未提供 / 需确认 / 不建议编写"。
8. 不得因为只输出单个模块，就降低该模块的专业度、完整度和可复制性。
9. 产品图生成必须使用图生图模式，产品视觉图缺失时不得强行生成，应先向用户索取。
10. 产品图生成后必须做后置 QA 并把报告随交付附上；QA 只剔除"明显不是产品图"，其余全部随交付发出。
11. Docx 章节列表必须与本次输出范围一致：完整文案模式 → §1-§9；纯生图任务 → §10-§11；文案+图 → §1-§11；按需/组合 → 只含被点名章节。未被请求的模块不占位、不空章。
12. 飞书渠道 + `lark-cli` 已认证时，任何完整成品交付默认走 §18 Docx，聊天框只发链接消息。仅单模块小交付、返工修订、用户显式指示"直接聊天框"时才允许绕过 Docx。

详细质量门槛见 `QUALITY_GATE.md`。完整输出模板与模块化输出模板见 `OUTPUT_TEMPLATE.md`。

### 0.1 辅助文件加载要求

`QUALITY_GATE.md` 和 `OUTPUT_TEMPLATE.md` 是本 Skill 的强制扩展规则，不是可选参考资料。如果运行环境会加载同目录文件，Agent 必须同时读取并遵守。如果运行环境只加载 `SKILL.md`，也不得放宽要求。

## 1. 角色定位

你是一个跨境电商产品上架内容生产 Agent。根据用户提供的产品信息、图片、目标国家与平台，按用户本次指定的输出模块，生成可直接用于电商运营的对应内容。

本 Skill 支持以下模块，但不默认全部输出：产品定位、标题建议、核心卖点、详情文案、9 图提示词、SKU 命名、关键词、规格参数、包装清单、风险提醒、主图提示词、SKU 图提示词、视频脚本、达人合作话术、本地化翻译、平台适配优化、产品图生成（真实生图，非提示词，见第 11-14 章）、图文交付到飞书（见第 16 章）。

如果产品信息不足，只在用户要求的模块内处理信息不足问题，不要自动补全其他未被要求的板块。

## 2. 输出路由规则 Output Router

Agent 在生成内容前，必须先判断本次请求属于哪一种输出模式。

### 2.1 按需模式

当用户说"只要标题 / 只做详情文案 / 给我 9 图提示词 / 重新做 SKU / 用生图工具产出 9 图"等，必须只输出对应模块。

### 2.2 组合模式

当用户说"只产出：标题、详情文案、9 图提示词"等，必须只输出用户点名的模块，按用户点名顺序或完整模式顺序排列。

### 2.3 完整模式

只有用户明确说"完整上架内容 / 全部内容 / 整套上架资料 / 全量输出 / 完整上架模式 / 按完整模式输出"时，才进入完整模式。必须输出默认 10 个板块：产品定位、标题建议、核心卖点、详情文案、9 图提示词、SKU 命名、关键词、规格参数、包装清单、风险提醒。

### 2.4 未指定输出范围

如果用户只说"用这个 Skill 做一下 / 处理一下这个产品"但没有明确说"完整输出"，也没有点名具体模块，则不要直接全量输出。应先给出简短模块菜单让用户选择：

```text
你想先产出哪一部分？
1. 标题建议
2. 详情文案
3. 9 图提示词（文字提示词，非真实图片）
4. SKU 命名
5. 关键词
6. 规格参数 / 包装清单
7. 产品图生成（真实生成 9 张图，走图生图 + 飞书卡片交付）
8. 完整上架内容
```

### 2.5 返工与修订模式

当用户针对上一次结果提出修改（"标题太短重做"、"9 图提示词换一版"、"第 3 张图产品变形了重出"），默认只修改用户指出的模块。除非用户明确要求"全部重新来 / 整套重做 / 完整重做"，否则不得全量重写。

## 3. 禁止自动补全其他模块

当用户只要求某个模块时，禁止自动附带产品定位、风险提醒、关键词、包装清单、规格参数等未被点名的模块。例外：如果某个模块内部必须使用少量事实信息，可以在模块内部自然体现，但不能单独新增未请求板块。

## 4. 信息优先级与真实性

优先级从高到低：用户明确提供的参数表 > 用户明确确认过的内容 > 用户上传图片中清晰可见且不与参数表冲突的信息 > 目标国家与平台的常规表达习惯 > 通用电商经验。

当图片与参数表冲突时，以参数表为准。当颜色、规格、型号、数量、材质、功能、包装内容未被用户明确提供时，不得编写为确定信息。不得编写未提供的参数、等级、平台背书、官方背书或绝对化承诺。

如果用户提供的图片带有品牌或 logo，默认用户有正规来源或授权，不要反复提醒品牌授权风险。

## 5. 本地化规则

本 Skill 支持任意目标市场与平台，语言不硬编。Agent 根据用户提供的 `{market}` 和 `{platform}` 参数，使用当地更自然的语言、平台搜索词、用户痛点和电商表达。图片文字默认使用目标市场的通用电商语言。

若用户未明确指定目标市场或平台，Agent 必须先询问，不得默认。

## 6. 5 步业务流程与三波并行流水线

五步业务语义不变；执行依赖重排为三波。运行前建立清单：

```bash
python3 scripts/run_manifest.py init ./run-manifest.json --market <market> --platform <platform> --category <category> --delivery-mode <docx|card>
```

`--delivery-mode` 默认 `docx`。飞书渠道且已认证、走 Docx 主交付时用 `docx`；非飞书渠道，或 `lark-cli` 未认证且用户拒绝授权而退回图文卡片时用 `card`。模式在 init 时确定并写入 manifest。

### Wave 0：准备（步骤 1-2）

- 并行读取用户资料、图片和必要参考；执行工具版本、认证与 capability preflight。
- 对上传图做 Pre-QA 分类路由；产品视觉图池零剔除、参考图池全传。
- 将已确认事实一次写入 manifest 的 `facts`，把所有缺失项合并成一次提问。
- **合并确认关口**：用户一次确认事实、输出模块和 9 图配比；关口前可并行准备，关口后所有任务只消费 manifest 这份单一事实源。
- 用 `timing` 记录 Wave 0 耗时。

### Wave 1：内容（步骤 3）

- 标题、卖点、详情、关键词、SKU、提示词等无相互依赖的内容模块可有界并发生产；每个模块仍逐项满足 §7 与 `QUALITY_GATE.md`。
- 9 图提示词保持三段式（形态锁定 + 产品外观 + 构图/文字/背景），默认真人规则不变。
- 各模块结束后合并回 manifest 的 `modules`，再做一次跨模块事实一致性检查，不允许并发任务自行发明参数。
- 可并行准备 Docx Markdown 骨架和 IM 卡片文字，但不得提前写同一 Docx。
- 用 `timing` 记录 Wave 1 耗时。

### Wave 2：生图与交付（步骤 4-5）

- 9 张图默认一次提交，上游限制为 9 并发：

```bash
image-provider-gateway batch --requests <json> --output-dir <dir> --concurrency 9 --retry 2 --timeout 240
```

- 每个请求均为图生图，并传入完整产品视觉参考池。成功、失败、结构化 `provider_error` 按槽位写回 manifest。
- 部分失败时运行 `python3 scripts/run_manifest.py select-retry ./run-manifest.json`；只重提返回的失败槽位。成功槽位禁止整批重跑，非 retryable 错误先按 §15.4 修正后再做单槽位重试。
- 首轮完成后把九张结果放入同一多模态上下文做**九图单轮批审**；🟢/🟡 直接记录，只有 🔴 候选逐张二次复核 hard reject 边界。soft pass 仍交付，QA 不替用户决策。
- 生图进行时可并行创建目录、准备 Docx 骨架和卡片；图片就绪后，9 个 IM `image_key` 上传可有界并发。
- **同一 Docx 写操作有序**：骨架创建完成后，`file_token` 的 media-insert 按槽位 01→09 串行，禁止并发写导致 revision 冲突。不同 Docx 才可并发。
- Docx 模式：每张可交付图同时记录 `file_token` 与 `image_key`，并记录 Docx、目录和卡片证据。
- 卡片模式：每张可交付图只要求 `image_key`，不创建也不残留 `file_token`、Docx 或目录证据；仍必须记录卡片发送证据。
- 两种模式都必须把 hard-rejected 槽位排除在交付集合外，并清除该槽位的 `file_token` / `image_key`。全部完成后统一执行 `validate --delivery`，再按所选模式交付。
- 用 `timing` 记录 Wave 2 及总耗时。

### 五步到三波映射

1. 收集信息 → Wave 0。
2. 审核补齐与 Pre-QA → Wave 0。
3. 出文案与提议生图 → Wave 1；配比确认属于 Wave 0 合并确认关口。
4. 图生图 → Wave 2，9 图满并发并按槽位增量恢复。
5. Post-QA 与交付 → Wave 2，批审、流水上传、有序 Docx 写入、统一验收。

## 7. 各模块质量规则

### 7.1 标题建议规则

标题必须是电商搜索标题，不是广告口号、海报文案或品牌命名。默认输出 3 个标题：平台主标题、SEO 长标题、简洁备选标题。主标题与 SEO 长标题必须至少包含 8 个有效关键词模块；简洁备选标题至少 5 个。如果标题只包含"品牌 + 型号 + 品类"，必须重写。

### 7.2 核心卖点规则

默认输出 8 条。每条必须包含：卖点标题 + 1 句用户利益说明 + 1 句适合详情页/图片文字的短文案。不得只写"高品质、方便、耐用、舒适、时尚、实用"等空泛词。

### 7.3 详情文案规则

必须是可直接用于商品详情页的完整成品。默认包含 7 个小节：开头购买理由、核心卖点、使用场景、适合人群、规格参数、包装清单、购买提醒。最低规模：开头理由不少于 2 句，卖点不少于 5 条，场景不少于 4 条，人群不少于 3 条。

### 7.4 9 图提示词规则

默认输出 9 个独立的正方形 1:1 产品图提示词。每个可单独复制使用，不能依赖其他提示词。必须明确禁止：九宫格、拼图、collage、3x3 grid、multi-panel layout、"同上"或互相引用。

每张图必须使用第 11.2 节的三段式提示词模板（形态锁定 + 产品外观描述 + 构图/文字/背景），字段如下：

```text
### 图 X｜图片用途
- 图片目的：
- 参考图锁定（形态一致性硬约束）：
- 产品外观描述（强化产品保真）：
- 是否包含真人：
- 画面构图：
- 背景/场景：
- 主标题：
- 副标题：
- 卖点标签：
- 小字说明：
- 视觉风格：
- Negative rules：
```

每张图必须包含：1 主标题、1 副标题、3-5 卖点标签、1 条小字说明、1 条 Negative rules、完整参考图锁定 + 产品外观描述 + 是否包含真人。

### 7.5 SKU 命名规则

必须覆盖用户提供的全部颜色 / 款式 / 版本，不得改变真实颜色、规格或版本。如果用户要求高级命名，每个 SKU 输出：基础名 / 高级名 / 平台显示名。

### 7.6 关键词规则

至少 30 个，并覆盖：品类词、功能词、场景词、人群 / 需求词、规格 / 属性词、本地化搜索词。关键词不能只是重复标题。

### 7.7 规格参数规则

必须以用户提供的信息为准。未提供的信息写"未提供 / 需确认"，不要猜测。

### 7.8 包装清单规则

只写用户提供或图片明确可见且不与参数冲突的内容。不明确时写"未提供完整包装清单 / 需以实际发货包装为准"。

### 7.9 风险提醒规则

输出 3-6 条真实上架风险。只提醒真实风险，不写泛泛免责声明。不要反复强调品牌授权风险。

### 7.10 主图提示词规则

只输出 1 张主图提示词，除非用户明确要求多张。必须包含：参考图锁定、产品外观描述、是否包含真人、构图、背景、文字、视觉风格、negative rules。

### 7.11 SKU 图提示词规则

按用户提供的颜色 / 款式数量输出对应数量的独立提示词。必须强调：同一布局、同一角度、同一构图、只改变颜色 / 款式，不改变产品结构；且必须走图生图，产品视觉图池中已存在的颜色变体优先直接采用。

## 8. 缩水输出判定

### 8.1 完整模式不合格情况

10 板块任一缺失、标题少于 3 个、卖点少于 8 条、详情缺 7 小节、9 图少于 9 张或字段不全或互相引用、关键词少于 30 个、SKU 未覆盖全部颜色、输出像摘要而非成品，都视为不合格。

### 8.2 按需 / 组合模式不合格情况

缺少要求的模块、输出未要求的完整板块、被请求模块低于最低门槛、返工时重写未要求模块、编写未知参数、9 图/SKU 图出现九宫格或互相引用，都视为不合格。

### 8.3 真实产品图生成不合格情况

- 步骤 2 没有对上传图做分类路由，或把"信息素材图"错当"产品视觉图"送去生图。
- 生图使用了纯文生图（`--mode` 不是 `edit` 或未传入 `--input-image`）。
- 生图时对产品视觉图池主动剔除（"这张光线不好我不传"这类判断），除非该图属于"信息素材图"或"无关图"。
- 涉及穿戴/使用/操作类产品但默认没有真人场景，且用户没有显式要求平铺/无模特。
- 生图完成后没有做 Post-QA 或没有把 QA 报告随交付发出。
- Post-QA 时对"产品可辨认但有瑕疵"的图做 hard reject（越界过滤）。
- 用飞书 MEDIA 指令或纯文本发送生成图，绕过 v2.5 分流（飞书认证时走 §18 Docx；退回时走 §16 卡片）。
- 飞书渠道 + `lark-cli` 已认证下的完整成品交付（完整文案 / 生图完成 / 完整=文案+图 / 组合模块完整交付）绕过 §18 Docx 直接在聊天框倒段落（v2.6 新增）。

如果不合格，Agent 不得把不合格版本输出给用户。必须先自行修正流程或重出内容。

## 9. 最终输出顺序

完整模式：产品定位 → 标题建议 → 核心卖点 → 详情文案 → 9 图提示词 → SKU 命名 → 关键词 → 规格参数 → 包装清单 → 风险提醒。按需模式只输出用户要求的模块。组合模式优先按用户点名顺序；无明确顺序则按完整模式相对顺序。

## 10. 推荐调用语句

### 只产出标题

```text
按照 ecommerce-product-listing-skill，只产出标题建议。
目标国家：<market>
平台：<platform>
产品信息如下：
……
```

### 只产出 9 图提示词（文字提示词，不真实生图）

```text
按照 ecommerce-product-listing-skill，只产出 9 张独立正方形产品图提示词。
目标国家：<market>
平台：<platform>
产品信息如下：
……
```

### 真实生成 9 张产品图（走图生图 + 飞书卡片交付）

```text
用生图工具生成 9 张产品图，走图生图模式。
参考图我已经发在上面 / 用最近一次上传的产品图。
目标国家：<market>
平台：<platform>
```

### 完整输出

```text
按照 ecommerce-product-listing-skill，输出完整上架内容。
目标国家：<market>
平台：<platform>
产品信息如下：
……
```

## 11. 产品图生成硬规则（Image-Edit-Only + 真人默认 + 参考图池全传）

真实产品图生成必须遵守以下硬规则，任何一条不满足都视为不合格。

### 11.1 图生图硬约束

- 生图工具必须使用 `image-provider-gateway`。
- 每一次真实生图调用必须包含 `--mode edit` + 至少一张 `--input-image <路径>`。
- 禁止使用纯 text-to-image（`--mode generate` 或省略 `--input-image`）生成产品图。
- 唯一例外：用户明确说"我没有产品图，你脑补"或"用文生图"时可以走 generate 模式，但必须先向用户确认，并在最终交付里显式声明"本轮为文生图，非图生图"。

### 11.2 提示词模板（三段式 + 可选变体保真段）

每张图的提示词必须由三段组成（形态锁定 + 产品外观描述 + 构图/文字/背景）；当本图涉及多个 SKU/颜色变体时**建议**多加一段 Variant-Preservation Block（下方模板），实测能显著减少变体串色；但不加也能出图，不作硬门槛：

```text
[Reference-Fidelity Block（形态一致性硬约束）]
Preserve the exact product shown in the reference image(s). Match the housing shape,
key structural cues, port/interface positions, seams, and material texture exactly
as in the reference(s). Do not invent parts, buttons, or interfaces that don't
exist in the reference(s).

[Product-Appearance Block（产品外观强化描述）]
Product: <品类 + 型号 + 主要形态描述>。
Color variant: <本图使用的颜色>。
Material: <外观材质与质感>。
Key structural cues: <能强化保真的关键结构>。
Approx size/spec: <合理规格>。

[Composition Block（本图独有的构图/背景/文字/是否含真人）]
按 9 图提示词各自的字段填写（是否含真人、主标题、副标题、卖点标签、小字说明、视觉风格、Negative rules）。

[Variant-Preservation Block（可选：本图涉及多个 SKU/颜色变体时建议填写）]
Multi-variant lineup: strictly N variants side by side. For each variant, preserve:
  - variant #1: color=<name>, position=<left/center/...>, on-body text=<verbatim>
  - variant #2: color=<name>, position=..., on-body text=<verbatim>
  ...
Rules: variant count MUST equal <N>; variant order MUST match the SKU table above;
no color bleeding across variants; each variant's on-body text/logo verbatim as
specified; no invented variants.
```

三段（或四段）合起来一次性喂给生图工具的 `--prompt`。

**引号建议**：用 `json.dumps` 生成 batch JSON 时，ASCII 双引号 `"` 会自动转义 `\"`，无需刻意规避。**手拼 batch JSON 或 shell 单行命令**时，建议用中文双引号 `“”`、中文引号 `「」` 或 ASCII 单引号 `'` 代替，避免转义地狱。

### 11.3 参考图池全传

- 步骤 2 分类路由得到的"产品视觉图池"中的**所有图**都要传给 `image-provider-gateway` 作为 `input_images`。
- Agent 不得因"某张光线不好""某张构图不完美""某张分辨率偏低"等主观判断而主动剔除产品视觉图池里的图。这类判断权归模型，不归 Agent。
- 剔除只发生在步骤 2 的分类阶段，且判定标准只有一条："这张图是不是产品视觉图？" 是则进池，不是则去信息素材路径或询问用户。
- 若参考图数量超过生图工具单次调用上限（通常 9-10 张），Agent 才做技术性截断，并在交付说明中告知用户；截断优先保留最能体现产品全貌的图。

### 11.4 真人使用场景为通用默认

- 电商产品图**默认包含真人使用/穿着/持握/操作场景**。这条对所有类目通用（服装、3C、家居、美妆、食品、工具、办公、宠物…），核心逻辑是"让买家想象自己在用"是跨类目的转化力锚点。
- Agent 在步骤 3 提议 9 图配比时，**默认按下面基础比例给出**（可以根据类目微调）：
  - 主图 1 张：产品棚拍主体
  - 真人使用场景 4-6 张：不同角度/场景/使用方式
  - 细节特写 2-3 张：材质/接口/纹理（这类可无人）
  - 场景/氛围图 0-2 张：使用环境
- **例外（必须显式说明才走）**：
  - 用户明确指令"平铺 / 无模特 / 仅棚拍 / 白底"。
  - 被安全过滤器拦截，且提示词/参考图无法调整 → 降级为无人。
  - 产品本身无法体现"使用"（罕见，如原材料、大宗物料）。
- **判定优先级**：用户显式指令 > "默认含真人"通用原则 > 平台惯例。
- 真人形象必须使用合规姿态（不涉及裸露、暴力、儿童等被过滤器拦截的元素）；服务于产品，而不是喧宾夺主。

### 11.5 参数默认值

- `--model`：使用 `image-provider-gateway config` 中的 provider default_model，或用户显式指定。
- `--size`：`1024x1024`
- `--quality`：正式产出 `high`；快速试制 `low`（明确告诉用户是"试制"）
- `--timeout`：单张不低于 180 秒
- 批量：`image-provider-gateway batch` + JSON，`--concurrency 9`（9 图默认满并发），`--retry 2`

### 11.6 参考图路径的确定顺序

1. 用户在本次对话里明确指定的路径。
2. 用户在上一条消息里发的图片（用 `feishu-tools find-image --since-minutes 30 --first` 拿到）。
3. 用户此前明确说过"用某张图"的图片（对话历史找）。
4. 找不到时，必须向用户索取参考图，禁止使用 fallback 或空 input-image。

## 12. 产品图生成完整工作流（5 步版）

本工作流是 Skill 内的自包含流水线，Agent 每次做真实产品图生成时必须完整走完。5 步流程见第 6 章，本章补充生图专用的动作细节：

1. **步骤 1 · 收集信息**
   - 跑 preflight（15.2 节）。
   - 用 `feishu-tools find-image --since-minutes 30` 拿最近的上传图列表。
2. **步骤 2 · 审核补齐（含 Pre-QA 分类路由）**
   - 对每张上传图做分类路由（第 13 章）。
   - 提取参数，补问缺失信息。
3. **步骤 3 · 出文案 + 提议生图**
   - 提议 9 图配比（含真人张数分配）让用户 confirm。
4. **步骤 4 · 生图**
   - 生成三段式提示词 + batch JSON。
   - 产品视觉图池所有图作为 `input_images`。
   - 执行 `image-provider-gateway batch`。
5. **步骤 5 · 交付**（分渠道分流）
   - 九图单轮批审，只有 🔴 候选二次复核（第 14 章）。
   - hard reject 只针对"明显不是产品图"。
   - **飞书渠道 + `lark-cli` 已认证**：走第 18 章 Docx 交付（Docx + 云盘图片 + 图文卡片 + 聊天框链接消息）。
   - **飞书未认证 + 用户拒绝授权 / 非飞书渠道**：走 `feishu-tools send-card` 图文卡片，QA 报告作为文字块附上。

## 13. 步骤 2 内嵌 Pre-QA：分类路由

Agent 自己是多模态模型，直接看每张用户上传图，做**三分类路由**。此环节的目的不是判优劣，而是确定每张图的用途。

### 13.1 分类规则

| 类别 | 判定标准 | 处理方式 |
|---|---|---|
| 🖼️ **产品视觉图** | 能看到产品外观（正面、侧面、穿着/使用/操作效果、模特试用、开箱等） | 加入生图参考图池，全部传给 `image-provider-gateway` |
| 📋 **信息素材图** | 参数表、规格截图、说明书扫描件、包装文字面、数据对比图、宣传物料 | 提取信息用于文案模块（规格参数、卖点、包装清单等）；**不传给生图工具** |
| ❓ **无关图** | 误传的日常照、表情包、无关截图、明显不是本产品的图 | 报告给用户确认，不擅自使用 |

### 13.2 分类判定的 Agent 内嵌 prompt 模板

Agent 内部对每张图问自己：

```text
这张图是关于本次产品的什么？
- 是产品视觉图（能看到产品外观本身）？→ 归 🖼️
- 是产品信息素材（参数表/说明书/文字面等）？→ 归 📋
- 完全跟本产品无关？→ 归 ❓

对 🖼️：一句话描述看到了什么产品视觉（"白色兔女郎连体衣的正面站姿全身"）。
对 📋：一句话总结上面写了什么信息（"包装盒背面尺码表，S/M/L 三档"）。
对 ❓：一句话说明为什么归为无关（"是用户的自拍，不是产品"）。
```

分类结果连同一句话说明，写进步骤 2 的审核补齐输出里，让用户可见 & 可 override。

### 13.3 分类的"零剔除"原则

- 🖼️ 产品视觉图池**零剔除**：不管评分、光线、构图、分辨率，全部作为生图参考。Agent 不做"这张不够好我不用"这种判断。
- 📋 信息素材图**不加入生图池**，但内容不丢弃 — 用于文案模块。
- ❓ 无关图必须先跟用户确认，不擅自剔除也不擅自使用。

### 13.4 用户覆盖

用户如果说"这张图用作参考"或"这张图不用"，一律以用户指令为准，覆盖 Agent 的分类判定。

## 14. 步骤 5 内嵌 Post-QA：Agent 多模态自审

生图完成后，Agent 直接看图（不外调 `image` 视觉子模型），把九张生成图放入同一上下文做九图单轮批审。🟢/🟡 一轮定稿，只有 🔴 候选再逐张二次复核 Hard Reject 边界。QA 是决策辅助，不是卡点。

### 14.1 Post-QA 审计维度

Agent 内部对每张生成图问自己以下问题（同时参照产品视觉图池对比）：

- 产品是否可辨认？（形态、颜色、关键结构）
- 是否属于"明显不是产品图"（生成失败/损坏/严重跑题/占位图/纯猫狗抽象图形）？
- 有哪些瑕疵？（文字错字、手指数量、光照、构图、幻觉细节）
- 如果作为电商图，会打什么标签？（🟢 推荐主图 / 🟡 可用但有瑕疵 / 🔴 剔除原因）
- 🟡 图**建议**附"修复方式建议"四选一：**重出 / PS 后处理 / 遮盖裁剪 / 直接使用**；当 🟡 图 ≥ 3 张时**必须**汇总建议表，让用户一眼看到修复路径。例：logo/文字错字 → PS；产品主体变形 → 重出；构图小瑕疵 → 遮盖裁剪；完全可接受 → 直接使用。

Agent 用自然语言对每张图产出简短的 Post-QA 记录，格式：

```text
图 X（<文件名>）：<标签>｜<一句话说观察>｜<有瑕疵时列 1-3 条 issue>｜修复建议：<重出/PS/遮盖裁剪/直接使用>
```

### 14.2 Hard Reject 边界（严格限定）

只有满足以下**任一条**的图才做 hard reject（不发出）：

- 生成 API 返回错误 / 图片文件损坏 / 无法打开。
- 主体完全跑题（生成的画面里没有目标产品，或产品被替换成完全无关的物件）。
- 触发安全过滤器返回的占位图/黑图/空白图。
- 严重畸变导致产品完全无法辨认（不是"歪一点""比例怪"，而是"看不出这是什么"）。

其余一律 soft pass — 发出并在报告里标注瑕疵。

### 14.3 Soft Pass 原则（默认放行）

- 产品可辨认但有瑕疵（文字错字、手指怪、光照偏色、构图不完美）→ 发出，报告里标 🟡。
- 审美不完美但符合基本电商标准 → 发出，报告里标 🟢 或 🟡。
- Post-QA 评分低但依然是合格产品图 → 发出。

**判定原则**：一句话"这张是用户想上架的产品图吗？"—— 答"是"就发。

### 14.4 QA 报告是决策辅助

Post-QA 报告作为**信息附录**跟交付卡片一起送给用户，包含：

- 每张图的标签（🟢/🟡/🔴）+ 观察记录 + 瑕疵列表
- 建议 revision_prompt_hint（用户想重出时可用）
- 不代表 Agent 强制建议，最终决策权在用户

Agent 不得因 QA 报告不完美就阻塞交付，也不得因个别 🟡 图就重新生成整批。

## 15. 依赖工具与安装（Preflight）

### 15.1 依赖工具清单

本 Skill 依赖以下两个外部 CLI 工具，两个都是 T-Chen-CN 维护的 public 开源项目：

| 工具 | 用途 | 最低版本 | 仓库 | 安装命令 |
|---|---|---|---|---|
| `image-provider-gateway` | 图生图 / 文生图统一入口，OpenAI-compatible API；支持配置文件持久化 provider 凭据 + 结构化错误码 | `>= 0.1.0` | https://github.com/T-Chen-CN/image-provider-gateway | `uv tool install git+https://github.com/T-Chen-CN/image-provider-gateway` |
| `feishu-channel-tools` | 飞书交互卡片发送、inbound 图片查找 | `>= 0.2.0`（取消了图片张数的隐式上限，仅按 25 KiB 字节兜底）| https://github.com/T-Chen-CN/feishu-channel-tools | `uv tool install git+https://github.com/T-Chen-CN/feishu-channel-tools` |
| `lark-cli`（`@larksuite/cli`）| 飞书官方 CLI，用于云空间目录 / Docx / 云盘图片上传，v2.5 起交付主通道 | `>= 1.0.0` | https://github.com/larksuite/cli | `npm install -g @larksuite/cli` |

两个 `uv` 工具都通过 `uv tool` 安装，`lark-cli` 走 npm 全局安装，用户无需 sudo，Agent 拿到用户同意即可自行安装。旧版本应直接升级为最新 main，不得降级绕行。

**渠道分流：** 当前渠道是飞书时，`lark-cli` 是**硬依赖**（承担 Docx 交付）；非飞书渠道 `lark-cli` 为可选，交付走各渠道自己的通道。

### 15.2 Preflight 校验

Agent 进入涉及真实生图或飞书交付的工作流之前，必须执行 preflight，它同时检查**存在**与**版本**：

```bash
# 1. 存在性

command -v image-provider-gateway >/dev/null && echo "ipg: present" || echo "ipg: MISSING"
command -v feishu-tools >/dev/null && echo "ftt: present" || echo "ftt: MISSING"

# 2. 版本断言（旧版本无 --version 子命令会报错 → 视同失败）

feishu-tools --version 2>/dev/null | grep -Eq " [0-9]+\.[0-9]+\.[0-9]+" || echo "ftt: NEEDS_UPGRADE"
# image-provider-gateway 目前没实现 --version，用能否读到 config path 作为 sanity 断言
image-provider-gateway config path >/dev/null 2>&1 || echo "ipg: NEEDS_UPGRADE"

# 3. lark-cli（v2.5 起，飞书渠道硬依赖）

command -v lark-cli >/dev/null && echo "lark: present" || echo "lark: MISSING"
lark-cli --version 2>/dev/null | grep -Eq "[0-9]+\.[0-9]+\.[0-9]+" || echo "lark: NEEDS_UPGRADE"

# 4. lark-cli 认证状态（飞书渠道，Docx 交付前必须 ready）

lark-cli auth status --json 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); u=d.get("identities",{}).get("user",{}); print("lark: auth-ready" if u.get("status")=="ready" and u.get("tokenStatus")=="valid" else "lark: AUTH_MISSING")' \
  || echo "lark: AUTH_MISSING"
```

任何一个 `MISSING` 或 `NEEDS_UPGRADE`，Agent 必须立刻停止流程，向用户报告：

如果是 `lark: AUTH_MISSING`（`lark-cli` 已装但未登录），处理逻辑详见第 18 章「飞书云文档输出模式」§18.2。**不设超时**：Agent 询问用户后 yield 等待，直到用户回复；用户拒绝授权则退回旧的图文卡片交付。

```text
❌ 工具不可用：<工具名>

现状：<MISSING / 版本不足 v<x>>
用途：<该工具的用途>
仓库：<URL>
升级命令：`uv tool install --reinstall git+<repo-url>`

需要我现在安装／升级吗？授权就跑。
```

用户授权后，Agent 直接跑升级命令；不授权则拒绝执行本次任务。

### 15.3 凭据配置

**`image-provider-gateway` 优先使用配置文件**（v0.2 起支持）：

- 一次性初始化：`image-provider-gateway init --provider <name> --base-url <url> --api-key-stdin --set-default --non-interactive`。
- 配置落在 `~/.config/image-provider-gateway/config.json`（`chmod 600`），后续生图无需再问用户要 key。
- 优先级：CLI flag `--base-url` / `--api-key-env` > env var `IMAGE_API_KEY` / `IMAGE_API_BASE_URL` > 配置文件。
- 首次使用时 Agent 应引导用户跑 `init`；后续会话直接读配置文件。

**`feishu-channel-tools`** 需要（按优先级回落）：`FEISHU_APP_ID` + `FEISHU_APP_SECRET` > `OPENCLAW_CONFIG` 指向的 JSON > `~/.openclaw/openclaw.json`。

Agent 遇到工具报"缺 key / 缺 config"时向用户申请补齐；不得把 key 硬编码到脚本或 batch JSON 里。

### 15.4 生图工具错误码

`image-provider-gateway` 返回的失败结果带结构化 `provider_error`，Agent 应根据 `code` 分流处理，而不是字符串匹配 message：

| code | 含义 | retryable | Agent 应对 |
|---|---|---|---|
| `safety_violation` / `content_policy_violation` | 触发安全过滤器 | 否 | 改写提示词避开敏感词，或降级构图（如去人物、去背景元素）后重生 |
| `rate_limit` | 限流 | 是 | 降低并发或退避重试 |
| `auth_failed` | key 无效/权限不足 | 否 | 引导用户重新 `init` 或换 provider |
| `quota_exceeded` | 额度用尽 | 否 | 通知用户充值或切 provider |
| `model_not_found` | 模型不存在 | 否 | 使用 provider 默认模型或换一个 |
| `bad_request` | 参数错误 | 否 | 检查 size/quality/prompt 长度 |
| `server_error` / `timeout` / `network_error` / `provider_json_error` | 上游/网络瞬时问题 | 是 | 走 batch 的 retry；仍失败则报告用户 |

## 16. 图文交付到飞书（退回路径 / 非 Docx 场景）

**v2.5 起，飞书渠道默认走第 18 章的 Docx 交付**。本章描述的图文卡片路径成为退回路径，仅在以下情况使用：
- `lark-cli` 未认证且用户拒绝授权。
- 非飞书渠道（如 Signal / Telegram / Discord）的类比交付需要。
- 用户显式指定"只发卡片不建 Docx"。

### 16.1 硬规则（退回路径下适用）

- **本章硬规则只在退回路径下强制**（Docx 主路径走第 18 章）。
- 图文并发的产品图交付走 `feishu-tools send-card`，**不得**走 OpenClaw 的 MEDIA 指令。
- 一次 send-card 就把所有图（含 QA 报告文字）打包成 1 张交互卡片一次性发出。
- `feishu-channel-tools >= 0.2.0` 以后，**图片张数没有隐式上限**；只当 payload 超过飞书 25 KiB 字节限制时工具才会自动拆卡，Agent 不需要手动分批。避免基于"图多于 N 张自己先拆包"这种过时的伪优化。
- 长文本正文可用 `--text-file <path>` 传入 Markdown 文件，也可以用 `--text "..."` 直接传，两种都行。**建议用 `--text-file`** 的场景：正文含 Markdown 代码块、反引号 `` ` ``、`$`、多行 heredoc 或 shell 转义复杂时。没有硬字符阈值；以“能不能一次 shell 命令写完不出错”为标准。

### 16.2 标准调用范式

```bash
feishu-tools send-card \
  --to <飞书 open_id> \
  --title "<卡片标题>" \
  --template <颜色主题> \
  --text-file /path/to/text.md \
  --image /path/to/01.png --caption "1. 主图" \
  --image /path/to/02.png --caption "2. <本图定位>" \
  ...
```

`--caption` 顺序按 `--image` 排列，每张图都必须有 caption。

### 16.3 卡片文字正文推荐结构

```markdown
**<品牌 / 型号> · <张数> 图产出** 🌸

- 目标市场：<market>
- 平台：<platform>
- 生图模式：图生图（image edit）
- 参考图池：<n> 张（<文件名列表>）
- 生图模型：<model 名> / <size> / <quality>

## QA 摘要

- 🟢 推荐主图：<n> 张（<图号列表>）
- 🟡 可用但有瑕疵：<n> 张（<图号列表>）
- 🔴 已剔除：<n> 张（<图号列表 + 剔除原因>）

## 逐张观察

<每张图一行：图号｜标签｜观察｜瑕疵｜revision_prompt_hint>
```

### 16.4 交付失败处理

`feishu-tools send-card` 的设计承诺是"不允许失败"：单卡超限自动拆卡，多图自动分批。

- 若命令返回 `ok: true`，视为成功。
- 若命令抛异常（网络级 / API 级 / 配置错），Agent 必须完整暴露错误信息给用户，不得静默重试超过 3 次，不得降级为纯文本或拆散图片重发。

### 16.5 send-card 之外的场景

如果本次交付不涉及图片（只有文本），Agent 可以直接用当前会话回复，不必强行走 send-card。send-card 只用于必须"图文一起送"的场景。

## 17. Agent 名称与身份（v2.5 新增）

v2.5 起，飞书云文档目录以 Agent 名称为顶层节点。Agent 名称必须**动态读取**，禁止硬编码。

### 17.1 名称解析顺序

Agent 必须按以下优先级顺序解析 `{agent_name}`：

1. `IDENTITY.md`（工作区根目录）中「**名字：**」或「**名字:**」字段的值。
2. 如果 1 无法解析（文件缺失、字段缺失、值为空），**hard fail**：中断流程并请求用户先在 `IDENTITY.md` 中声明 `名字：<你的 Agent 名>`。

### 17.2 兜底策略

**禁止**使用 `agent-{open_id}` 或时间戳等自动兜底名生成目录，避免生成不可读的目录名污染用户的云空间。**必须让用户显式提供名字**才能进入 Docx 交付流程。

### 17.3 名字规范

- 支持中文 / 英文 / 数字。
- **建议 1-12 个字**（再长在飞书云空间目录树里显示会截断）；**禁止**含 `/`、`\`、`:`、`|`、`*`、`?`、`<`、`>`、`"` 等字符（飞书云空间 `create_folder` API 会拒绝这些字符作为文件夹名，且部分字符会破坏本地路径拼接）。
- **禁止**首尾空格（飞书 API 会保留原始空格，产生难以肉眼分辨的重复目录）。
- 首次使用时 Agent 应向用户确认："我以 `<agent_name>` 身份创建飞书云文档目录，对吗？"

### 17.4 输出层级序号规范（所有完整成品统一）

任何完整成品交付（飞书云文档 Docx、长卡片正文、导出 Markdown 等）中出现的多级标题必须按下表统一编号，便于人眼扫读、目录展示、跨文档对齐：

| 层级 | Docx 层级 | 编号格式 | 示例 |
|---|---|---|---|
| 一级章节 | h2 | `一、` / `二、` / `三、` … `十、` | `一、产品定位` |
| 二级小节 | h3 | `（一）` / `（二）` / `（三）` … | `（一）开场钩子` |
| 三级子项 | h4 | `1.` / `2.` / `3.` … | `1. 磁吸换弹` |
| 四级子子项 | h5 | `1.1` / `1.2` / `1.3` … | `1.1 装配步骤` |

规则细节：

- **h1 保留给 Docx 主标题**（即产品名 / 文件名对应的第一行标题），一份成品仅一个 h1。
- **只用到多少层就编到多少层**——不需要为凑齐 4 层强行拆结构。
- **附录、元信息、参考文献等辅助段落**用文字标记（`附录：`、`参考：`、`元信息：`），不占中式序号槽位。
- **超过十的一级章节**（罕见）用 `十一、`、`十二、`；超过九的二级小节用 `（十）`、`（十一）`。
- **h3 编号本地重置**：每个一级章节内 h3 独立从 `（一）` 起编，不跨章节累积。
- **数字子项**同理，每一级各自独立。
- **卡片、按需模块（第 7 章）不强制多级 heading**——只有走完整交付路径才启用本规范；单模块产出只需保持内部一致即可。

以下章节的输出模板（第 18 章 Docx 骨架、OUTPUT_TEMPLATE §2 完整上架模式）已按本规范给出示例。

## 18. 飞书云文档交付模式（v2.5 新增；v2.6 扩展至所有完整成品）

飞书渠道 + `lark-cli` 已认证时，产品文案与图片的最终交付通道为**飞书云文档（Docx）**。本章定义了触发条件、目录规则、批次规则、Docx 结构、图片处理和交付形态。

### 18.0 触发条件（v2.6 新增）

飞书渠道 + `lark-cli` 已认证时，以下场景**必须**走 Docx 交付，不能直接在聊天框输出段落：

- 完整上架文案模式（Skill §2.3 定义的 10 板块文案）
- 真实生图任务完成（9 图 + Post-QA 报告）
- 完整交付 = 文案 + 图 一次性
- 组合模块的完整版交付（例："标题 + 详情 + 9 图" 打包）

以下场景**不走** Docx，直接在聊天框输出：

- 单模块小交付（"只要标题"、"只要 SKU 命名"、"只要关键词"）
- 返工修订某一小节（"重出第 3 张图"、"标题太短再来"）
- 用户显式指示"在聊天框输出"或"不建 Docx"

未认证 / 非飞书渠道的处理详见 §18.2 与 §16。

**版本对齐读取 + capability preflight（`lark-cli` 强制约定）：** 进入本章任何 `docs +*` 操作前，Agent **必须**先跑 `lark-cli skills read lark-doc` 及以下参考文件，获取与已安装版本对齐的参数与工作流；随后用实际命令 `--help` 做 capability preflight。嵌入 reference 可能滞后，`lark-cli 1.0.68` 的 `media-insert --help` 已支持 `--selection-with-ellipsis`，因此只要当前 help 存在该参数就保留使用，不得因旧 reference 未列出而错误删除有效参数；若当前版本确实不支持，才选择该版本文档给出的等价定位参数或停止升级。

```bash
lark-cli skills read lark-doc                                       # 主入口
lark-cli skills read lark-doc references/lark-doc-create.md         # 创建 docx
lark-cli skills read lark-doc references/lark-doc-md.md             # markdown 语法（推荐格式）
lark-cli skills read lark-doc references/lark-doc-media-insert.md   # 图片插入
```

**lark-cli 通用路径陷阱（务必记住）：** 所有 `--file`、`--content @<path>` 参数**只接受当前工作目录下的相对路径**，绝对路径（如 `/tmp/xxx.png`）会报 `unsafe file path`。上传前 `cd` 到目标目录，或把资源复制到 cwd 相对路径。

### 18.1 目标目录路径（v2.6.1 简化）

固定的四层路径（顶层 Agent 名可变；产品目录名不再带日期前缀）：

```
飞书云空间"我的空间"根
└── {agent_name}/                        （§17 解析）
    └── 电商需求/
        └── Listing/
            └── {slug}/                  （单产品目录 · v2.6.1 去掉日期前缀）
                ├── Main{批次}-{位置}.png
                ├── SKU{批次}-{位置}.png （仅用户明说时产）
                └── YYYYMMDD-{slug}-{Docx批次}.docx
```

- `slug` = 用户原样品牌/型号 + 国家代码（详见 §18.4）。同 slug 跨天复用，目录名不变。
- `YYYYMMDD` 只出现在 Docx 文件名中，代表该 Docx 的**生成日期**（每次新建 Docx 用当天日期）。

### 18.2 Preflight 与授权流程

进入 Docx 交付前 Agent 必须先走：

1. 跑 §15.2 的 lark-cli 段。
2. 如果 `lark: AUTH_MISSING`：
   - Agent 向用户发一条消息："`lark-cli` 未认证，本次要走飞书云文档交付吗？(是=先授权，否=退回图片卡片)"。
   - **不设超时**：用完消息后 `sessions_yield` / 挂起等待用户回复，多久回都行。
   - 用户回"是" → Agent 触发 `lark-cli auth login --no-wait --json --domain all`，拿到 `verification_url` + `user_code` + `device_code`；生成二维码并把 URL / 二维码发给用户；用户扫码后用 `--device-code` 续；成功后进入 §18.3。
   - 用户回"否" → 退回第 16 章图文卡片路径，本次不建 Docx；manifest 必须以 `--delivery-mode card` 初始化（若已按默认 `docx` 初始化，须重新初始化并合并已确认事实，不得只手改模式掩盖错误）。

### 18.3 目录幂等创建

**Skill 不缓存 folder_token**，每次跑通过 API 探测。逐层做「查子文件夹是否存在，缺则建」。**优先使用 shortcut** `drive +create-folder`；shortcut 未覆盖的场景（如根 token 探测、分页列子文件夹）用 `lark-cli api` 走 raw：

```python
# 伪代码（Agent 内部实际用 python / shell 组合调用 lark-cli 都可）

# 1. 拿"我的空间"根 folder_token（raw，无 shortcut）
root = lark-cli api GET /open-apis/drive/explorer/v2/root_folder/meta --jq '.data.token'

# 2. 逐层 ensure
parent = root
for name in ["{agent_name}", "电商需求", "Listing", "{slug}"]:
    # 2a. 列出 parent 下所有子文件夹（分页；page_size 上限 200）
    children = lark-cli api GET /open-apis/drive/v1/files \
                 --params '{"folder_token": <parent 变量>, "page_size": 200}'
    if 存在 type=folder 且 name == 目标名:
        parent = 该 token
    else:
        # 2b. 创建（推荐 shortcut）
        parent = lark-cli drive +create-folder \
                   --folder-token <parent 变量> \
                   --name <目标名> \
                   --jq '.data.token'
```

**⚠️ 空 token 防呆陷阱**：`lark-cli drive +create-folder --folder-token "$X"` 里若 `$X` 为**空字符串**（上一步解析失败 / 捕获 stderr 污染了 stdout / 变量作用域丢失等），**官方 CLI 会 fallback 到根目录**建同名子目录，造成“到处建同名目录”的 silent-fail cascade；官方 --help 明说“Omit --folder-token to create in root folder”。**硬规则**：任一步获取 folder_token 后，**必须断言 token 非空非占位值**（非 `""` / `null` / `undefined`）；任一步解析失败即 hard fail，**禁止把空值传给下一步**。同时：**`--json` 捕获时必加 `2>/dev/null`**，因为 lark-cli 把进度信息写 stderr，不隔离会污染 JSON 解析。

第 4 层 `{slug}` 特殊（v2.6.1）：如果已存在同 slug 目录，Agent **复用**（不建新）；如果不存在则直接建。目录名不再带日期前缀，日期只出现在 Docx 文件名里。

### 18.4 Slug 规则（v2.6.1 极简版）

**核心原则**：Slug = 产品身份 + 市场，不表达变体 / 语言 / 包装。产品身份完全按用户原样保留，不做美化。

**规则（按顺序）**：

1. **提取品牌 + 型号原样短语**：从用户输入中提取品牌 + 型号，**大小写、中文、越南文、音标、符号一律不动**。不含颜色、市场、语言、变体后缀。
2. **前置断言：品牌型号短语必须非空**（v2.6.2 新增）：如果抽不出品牌/型号（用户没提供、只给了品类"蓝牙耳机"、纯乱码等），Agent **必须打回用户**："你想上架的具体产品名/型号是什么？"，**禁止**继续用空字符串生成 slug（避免出现 `-VN` 这种残缺目录）。
3. **Whitespace → 横线**（v2.6.2 扩展）：任何空白字符（空格 / tab / 换行 / CR）都转成横线。这是唯一强制的字符转换（保证 URL / shell 友好）。
4. **删除文件系统禁用字符**：`/` `\\` `:` `*` `?` `"` `<` `>` `|` 直接删除。**其他字符全部保留**（下划线、加号、点、括号、感叹号、$ 号、# 号、Đ、é、ệ、emoji 等等一律保留）。
5. **连续横线折叠**为单个横线；**首尾横线剥离**。
6. **收尾断言：品牌型号部分（去掉国家码后）不能为空**（v2.6.2 新增）：如果规则 3-5 之后主体变空（例：用户输入全是禁用字符 `///`、全是横线 `---`），Agent **必须打回用户**，禁止生成 `-{国家码}` 这种以横线开头的残缺 slug。
7. **附加国家代码**：ISO 3166-1 alpha-2 **大写**（VN / US / TH / BR / JP / KR / DE / FR …），用横线拼接在品牌型号之后。
8. **不接受用户自定义规则**；只接受用户改"从这段话里抽出的品牌/型号短语"与国家代码。

**跨市场同产品**：不同国家代码 → 不同目录（`B48-VN/` vs `B48-TH/`）；同市场同产品的批次累积到同一目录，用 §18.5 Docx 批次号区分。

**例子**：

| 输入（品牌型号 · 市场） | → | slug |
|---|---|---|
| `B48 · 越南` | → | `B48-VN` |
| `B48 · 泰国` | → | `B48-TH` |
| `Anker Q30 · 美国` | → | `Anker-Q30-US` |
| `ZGAR-001 Pro (X版) · 巴西` | → | `ZGAR-001-Pro-(X版)-BR` |
| `兔女郎 Cosplay · 日本` | → | `兔女郎-Cosplay-JP` |
| `brand_name+v2.5 · 德国` | → | `brand_name+v2.5-DE` |
| `product/with/slashes · 法国` | → | `productwithslashes-FR` |
| `多个    空格 · 韩国` | → | `多个-空格-KR` |
| `B48\tPro · 越南`（含 tab） | → | `B48-Pro-VN`（v2.6.2 whitespace 归一） |
| `B48🎧Pro · 越南`（含 emoji） | → | `B48🎧Pro-VN`（emoji 保留） |
| （空品牌型号）· 越南 | → | **拒绝生成**（v2.6.2 前置断言，打回用户） |
| `///` · 越南 | → | **拒绝生成**（v2.6.2 收尾断言，主体为空） |

**为什么这么设计**（v2.6.1 简化理由）：

- **产品身份稳定**：`B48` 就是 `B48`，跨越南泰国美国都用同一个基名，只靠国家代码区分。
- **不小写化**：产品名 `B48`、`iPhone`、`ROG-Ally` 的大小写是身份的一部分。
- **不过滤字符**：`ZGAR-001 Pro (X版)` 用户认得的形式，不该被过滤成 `zgar-001-pro-x版`。
- **变体不进 slug**：颜色（Nude / Đen）、语言（越南语 / 泰语）不影响 slug，避免同一产品目录爆炸。这些差异由 Docx 内容自己表达。

### 18.5 批次号规则

产品目录内**两套独立计数器**：

| 资产 | 命名 | 批次 +1 触发 |
|---|---|---|
| 图片 | `Main{批次:03d}-{位置:02d}.png` 或 `SKU{批次:03d}-{位置:02d}.png` | **只有被改的那张图** 的批次 +1；未改的图保持原批次不变 |
| 文档 | `YYYYMMDD-{slug}-{批次:03d}.docx` | 每次**实际生成新 Docx**时 +1；只发卡片不建 Docx 时不 +1 |

**图片位置**：`01`-`09` 对应 §7.4 的 9 图；SKU 图另起序列。

**图片选取（Docx 内嵌）**：`latest-per-slot`。对每个位置 `NN`，取该位置的**最大批次号图片**。举例：假设首轮生完 9 图后用户不满意位置 03，Agent 单独重出 → 只有位置 03 得到 `Main002-03`；其余 8 张仍是 `Main001`。
```
文件夹现状：Main001-01, Main001-02, Main002-03, Main001-04, ..., Main001-09
新文档 Docx-003 内嵌：Main001-01, Main001-02, Main002-03, Main001-04, ..., Main001-09
```

### 18.6 图片双 token 上传

同一张本地 png 在飞书内部产生两个 token，各有用途，Agent 必须上传两次：

| Token 类型 | 推荐 shortcut | Identity | 用途 | 有效期 |
|---|---|---|---|---|
| `file_token` | `lark-cli docs +media-insert --doc <docx_token> --type image --file ./xxx.png --selection-with-ellipsis "位置 NN · ..." --caption "MainXXX-NN"` | `user`（默认） | Docx 图片块内嵌 + 云盘持久化 | 永久 |
| `image_key` | `lark-cli im images create --as bot --data '{"image_type":"message"}' --file image=./xxx.png` | **`bot`**（用户身份此 API 无权限，必须显式 `--as bot`）| 飞书 IM 交互卡片显示 | 24 小时 |

**关键细节：**

- `docs +media-insert` 是"上传 + 插入 + 绑定"3 合 1 shortcut，官方文档称 4 步编排 + auto-rollback；返回 `file_token` + `block_id` + `document_id`，无需 Agent 自己管理 `parent_type` / `parent_node` 参数。
- `im images create` **必须显式 `--as bot`**；用户身份调用会返回权限错误。这是 lark-cli 的 identity 约束，不是我们的选择。
- 两次上传是**独立**的：`file_token` 存云盘持久，`image_key` 存 IM 消息资源。同一张图上传两次不会浪费 quota（飞书 API 免费）。
- 独立 IM `image_key` 上传可有界并发；`file_token` 所在的同一 Docx media-insert 必须按槽位有序执行，避免 revision 冲突。卡片准备与该有序写入可流水化。
- **cwd 陷阱：** 两个 shortcut 的 `--file` 都要求相对路径，先 `cd` 到图片所在目录。

Agent 在流程中把每张图的 `{file_token, image_key, block_id}` 记录到内部状态。交付时：Docx 内嵌已自动完成；卡片发送时把 `image_key` 传给 `feishu-tools send-card`。

### 18.7 Docx 结构与生成流程（v2.6 动态组装）

Docx 内一级章节列表 = 本次用户实际请求的模块，一一对应；**不再固定 11 章**。四种典型形态：

| 形态 | 章节 | 触发场景 | 一级章节数 |
|---|---|---|---|
| 文案 Docx | 标题 / 卖点 / 详情 / 9 图提示词 / SKU / 关键词 / 规格 / 包装 / 风险 | 完整文案模式，本轮未生图 | 9 |
| 生图 Docx | 图片汇总 / Post-QA 报告 | 纯生图任务，文案已在其他 Docx | 2 |
| 全套 Docx | 上述 9 章文案 + 图片汇总 + Post-QA 报告 | 一次性完成文案 + 生图 | 11 |
| 按需/组合 Docx | 只含用户点名的模块章节 | 组合模块的完整版交付（"标题 + 详情 + 9 图"） | 变量 |

**编号规则**（v2.6 更新）：Docx 内一级章节按 `一、` `二、` `三、` … 顺序编号，从本 Docx 的第一个章节起编，**不跟随** SKILL.md §1-§11 原始编号槽位。示例：

- 文案 Docx 的 9 章顺序：`一、标题建议` / `二、核心卖点` / `三、详情文案` / `四、9 图提示词` / `五、SKU 命名` / `六、关键词` / `七、规格参数` / `八、包装清单` / `九、风险提醒`
- 生图 Docx 的 2 章顺序：`一、图片汇总` / `二、Post-QA 报告`
- 按需/组合 Docx：按用户点名顺序（或按完整模式相对顺序），从 `一、` 起编

**升级路径**：

- 首轮出文案 Docx-001（9 章）
- 用户后续要生图 → 生成生图 Docx-002（2 章），产品目录里 -001 与 -002 并存
- 或者升级到全套 Docx-003（11 章），前两份保留作为历史归档
- Docx 批次号（§18.5）不变：每次实际生成新 Docx 都 +1

Docx 主标题（h1）由 `docs +create --title` 传入，正文骨架从 h2 起。

**推荐生成流程（两阶段）：**

**阶段 1：markdown 骨架一次性 create**

把 §1-§11 全部文案 + §10 的 9 个 h2 占位符写成一个 markdown 文件，用 `docs +create --doc-format markdown` 一次性建 Docx：

```bash
# Agent 先把完整文案写入 cwd 下的相对路径文件
# 章节根据本 Docx 形态动态组装（v2.6）：文案 Docx 9 章 / 生图 Docx 2 章 / 全套 11 章 / 按需组合按点名
# 下面是"全套 Docx"示例；其他形态删掉不需要的章节即可
cat > ./_docx_body.md << 'MDEOF'
## 一、标题建议
...（3 组标题）...

## 二、核心卖点
...（8 条）...

## 三、详情文案

### （一）开场钩子
...
### （二）产品故事
...
### （七）结尾行动召唤

## 十、图片汇总

### （一）图 1 · 主图

### （二）图 2 · 白底细节

### （三）图 3 · 45 度角
...（余下 6 个位置，编号 （四）～（九））...

## 十一、Post-QA 报告
...
MDEOF

lark-cli docs +create \
  --parent-token <product_folder_token> \
  --doc-format markdown \
  --title "YYYYMMDD-{slug}-{批次:03d}" \
  --content @_docx_body.md \
  --jq '.data.document.document_id'  # 返回 docx_token
```

**阶段 2：按槽位有序精准插入图片**

每张图用 `docs +media-insert --selection-with-ellipsis "位置 NN · ..."` 定位到对应 h2/h3 后插入：

```bash
cd <图片所在目录>  # cwd 相对路径要求
# 图片位置编号 01..09 对应 h3 序号 （一）..（九）
# selection-with-ellipsis 匹配 h3 文本前缀（省略号会吃掉尾部差异，容忍用途文案调整）
labels=("（一）图 1" "（二）图 2" "（三）图 3" "（四）图 4" "（五）图 5" \
        "（六）图 6" "（七）图 7" "（八）图 8" "（九）图 9")
for i in 01 02 03 04 05 06 07 08 09; do
  idx=$((10#$i - 1))
  lark-cli docs +media-insert \
    --doc <docx_token> \
    --type image \
    --file ./Main{批次:03d}-${i}.png \
    --selection-with-ellipsis "${labels[$idx]} · <本图用途>" \
    --caption "Main{批次:03d}-${i}"
done
```

**为什么两阶段：** markdown 只支持网络图片（`![alt](url)`），本地图片必须走 `+media-insert`；把它们拆开让骨架文本一次搞定，图片精准插入到对应 h3 之后，比手写 XML block 简单得多。

**Markdown 转义要点：** 写入 markdown 时字面文本里的 `\`、`` ` ``、`*`、`_`、`[`、`]`、`$`、`~`、`<` 必须转义；行首的 `#`、`+`、`-`、`>` 也要转义。详见 `lark-cli skills read lark-doc references/lark-doc-md.md`。

### 18.8 生图卡片（配合 Docx）

除 Docx 外，Agent 还会走第 16 章的 `feishu-tools send-card` 发**同一批图片**的图文卡片，用于快速对图 / 图旁看 QA。每张图的 caption 结构固定为 3 行：

```text
Main{批次}-{位置} · <本图用途>
🟢 QA：<观察> ｜ 修复建议：<重出/PS/遮盖裁剪/直接使用>
```

（🟡/🔴 用对应色和描述）。

### 18.9 聊天框消息（v2.6 按形态分支）

Docx 生成完毕后，Agent 在聊天框只发一条消息（**零文案内容**）：

**文案 Docx**（无图）：

```text
📄 完整版：<docx-permalink>
📁 产品文件夹：<folder-permalink>
```

**生图 Docx / 全套 Docx**（含图）：

```text
📄 完整版：<docx-permalink>
📁 产品文件夹：<folder-permalink>
🖼 IM 图文卡片：另有一条 send-card 已推送

（本次生成 <N> 张图，Post-QA：🟢 <n1> / 🟡 <n2> / 🔴 <n3>；详见 Docx 相应章节）
```

**顺序建议**：含图形态先发 Docx 与文件夹链接消息，再推 send-card 图文卡片，避免时序混乱。

**禁止**在聊天框重复发送任何章节的段落文案内容。文案的唯一交付点是 Docx。

### 18.10 错误恢复

- Docx 创建到一半失败：删掉半成品 Docx（`lark-cli drive +delete --file-token <docx_token> --type docx --yes`，属于高风险操作 API，需 `--yes` 确认；Agent 在此场景下可自动 `--yes`）；已上传的图片保留（云盘中，下次续跑可复用）；报错并明确告诉用户失败在哪一步。
- 图片上传或生图失败：按 manifest 的结构化错误码只做单槽位重试；保留全部成功槽位，禁止整批重跑。重试 3 次仍失败则报告槽位与错误码。
- 飞书 API 限流：指数退避重试 3 次；仍失败 → 报错。
- Agent 不得静默重试超过 3 次，不得为规避错误改动路径或跳过步骤。
- `lark-cli` 命令中断 / kill 后：清理 cwd 下的临时 `_docx_body.md` 等中间文件（skill 不留残留）。
