# Ecommerce Product Listing Quality Gate

最终交付前只检查本次请求覆盖的模块，不用未请求模块阻塞交付。

## 1. 范围路由

- `task_scope=content`：expected_count=0，只验内容与 Docx/目录；不要求图片、QA、token、card。
- `task_scope=image`：验图片合同、QA、token 与卡片。
- `task_scope=full`：同时验完整内容双语与图片交付。

- 按需与组合任务只产出点名模块；revision 只改指定模块或槽位。
- 泛化产品图请求：`plan_mode=default_full`，默认完整方案 9 张。
- SKU 图、卖点图、指定图型：`plan_mode=custom`；返工槽位：`plan_mode=revision`。
- custom/revision 数量不明确时，先给槽位清单 + 总数，用户确认后记 `confirmed_by_user=true`。

## 2. 数量契约

- default_full 验收 9/9；custom/revision 验收 N/N，N 来自 `expected_count`。
- hard reject 不得变成少交理由，必须补替代槽位。
- 短交付先由可信调用方验证用户消息，再用 `set-short-delivery-approval` 记录确认原文、author/provider/channel/message_id 与 actual/expected；finalize 只能消费已有审批。

## 3. 真实性

- 未提供的材质、尺寸、等级、功能、包装、认证不得写成事实。
- 冲突时按“参数表 > 用户确认 > 图片清晰可见 > 市场惯例”处理。
- 绝对承诺、官方背书和医疗功效必须有证据。

## 4. 本地化与中文对照

- `docx_text` 模块登记到 requested_docx_modules 并逐项验收；internal/non_text 不参与正文双语验收。非中文完整 Docx 默认目标语言原文 + 逐项紧邻中文对照。
- 中文市场不重复对照。
- manifest 记录 localization_policy / target_language / docx_language_mode；显式语言优先，未给语言时按 market 判断中文与否，非中文通用默认 bilingual。`--monolingual` 需要用户确认；中文不重复。数据区分 `source_text` / `zh_reference` / `render_text`。
- 图片实际渲染文字只允许目标市场语言；中文对照不得传入生图 prompt，prompt 只能取 `render_text`。

## 5. 标题

默认 3 个：平台主标题、SEO 长标题、简洁备选。关键词自然覆盖，不写未知参数，不把广告口号冒充搜索标题。

## 6. 卖点与详情

- 核心卖点默认 8 条，每条含利益说明和可用短文案。
- 完整详情默认覆盖购买理由、核心卖点、使用场景、适合人群、规格、包装、购买提醒。
- 单模块也必须是可复制成品，不输出分析过程。

## 7. SKU 与关键词

- SKU 覆盖用户提供的全部颜色、款式、尺寸、版本和套装。
- SKU 图保持同布局、角度和构图，只改变确认过的变体。
- 完整关键词模块默认至少 30 个并覆盖品类、功能、场景、人群、属性和本地搜索词。

## 8. 图片计划与提示词

- 每个动态槽位有明确用途，独立可执行，不互相引用。
- prompt 为三段式：形态锁定 + 产品外观 + 构图/文字/背景。
- 禁止九宫格、拼图、3x3 grid、collage、multi-panel layout。
- 默认真人规则适用于能自然展示使用的产品；用户指令优先。

## 9. Pre-QA

- 产品视觉图：加入参考池，参考图池全传，不因光线或构图主观剔除。
- 信息素材图：提取事实，不传生图工具。
- 无关图：向用户说明并确认。

## 10. 图生图

- 真实产品图默认使用 `image-provider-gateway >= 0.1.0` 的图生图入口。
- 每个请求使用 edit 模式并带产品视觉参考图；文生图必须有用户明确批准。
- 成功槽位复用；结构化 retryable 错误只做单槽位重试，禁止整批重跑。
- 并发按实际 N 与上游限制设置，不写死数量。

## 11. Post-QA

- 全部结果做 single-round 批审；默认 9 张即九图单轮批审，只有 🔴 候选二次复核。
- hard reject：API/文件失败、损坏、严重跑题、安全占位、产品完全不可辨认。
- soft pass：产品可辨认但有文字、手指、光照或构图瑕疵。
- QA 是决策辅助，不替用户决策；🟡 图 ≥ 3 张时必须有汇总建议表。

## 12. Manifest

- 动态槽位必须精确匹配 `expected_count`；`plan_mode` 为 default_full/custom/revision。
- 子任务只用受控 CLI，不手改 JSON；replacement 必须在合同槽 rejected 后用 `add-replacement-slot` 创建并记录 `replaces_slot`。
- 文件锁、保留 mode 的原子替换、深度 `schema_version` 校验、`manifest_id` / `generation` / `revision` 冲突防护不得绕过。相对图片路径以 manifest 父目录为基准；并发子任务 mutation 强制传 revision + manifest_id + generation。
- 图片 scope 的 QA 记录 timezone datetime `reviewed_at`、`reviewed_slot_ids`、`reviewed_count`，覆盖所有最终 success/rejected/replacement 候选；timings、PNG/JPEG/WebP/GIF 与 token 证据完整。

## 13. Docx

- 章节镜像本次输出范围，不放空章。
- 非中文市场双语项逐项相邻，不能把整段中文集中放在文末。
- 同一 Docx 写操作有序；图片按实际动态槽位顺序插入。
- `file_token` 用于 Docx，`image_key` 用于 IM，两者用途不可混淆。

## 14. 卡片

- card 模式只发卡片，要求 `image_key` 和发送证据。
- 不得残留 `file_token`、Docx token/permalink 或目录 permalink。
- hard-rejected 槽位不得进入卡片或保留 token。

## 15. 飞书 Preflight

- 写入前读取与已安装版本对齐的 lark-doc 指引，再做 capability preflight。
- `media-insert --help` 支持 `--selection-with-ellipsis` 时使用它；不因旧 reference 删除有效参数。
- 未认证且用户拒绝授权时，明确退回图文卡片，不静默中断。

## 16. 最终结论

统一执行 `validate --delivery`。只有 N/N 或有用户明确短交付 override 才可完成；失败时只修正受影响模块/槽位，不减少约定数量，不隐藏 QA 或交付错误。
