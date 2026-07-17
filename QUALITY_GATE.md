# Ecommerce Product Listing Quality Gate

最终交付前只检查本次请求覆盖的模块。图片只做生图前 Pre-QA；生成后不做视觉质量审核。

## 1. 范围路由

- `task_scope=content`：expected_count=0，只验内容与 Docx/目录，不要求图片、token 或卡片。
- `task_scope=image`：验图片生成状态、token 与卡片。
- `task_scope=full`：同时验内容与图片交付。
- default_full 默认完整方案 9 张；custom/revision 使用确认后的动态 `expected_count`。

## 2. 数量与状态契约

- 每个约定槽位最终只能是 `success` 或 `failed`。
- `success + failed = expected_count`；失败不伪装成成功，也不从序号中消失。
- `success` 按序号直接交付；`failed` 按序号标记“生成失败”。
- 不因生成后的视觉判断触发补图、替换图或重做。

## 3. 真实性

- 未提供的材质、尺寸、等级、功能、包装、认证不得写成事实。
- 冲突按“参数表 > 用户确认 > 图片清晰可见 > 市场惯例”处理。
- 绝对承诺、官方背书和医疗功效必须有证据。

## 4. 本地化与中文对照

- `docx_text` 模块登记到 requested_docx_modules 并逐项验收；internal/non_text 不参与正文双语验收。
- 非中文完整 Docx 默认目标语言原文 + 逐项紧邻中文对照；中文市场不重复。
- 数据区分 `source_text` / `zh_reference` / `render_text`。
- 中文对照不得传入生图 prompt，prompt 只能取 `render_text`。

## 5. 标题

默认 3 个：平台主标题、SEO 长标题、简洁备选。关键词自然覆盖，不写未知参数。

## 6. 卖点与详情

- 核心卖点默认 8 条，每条含利益说明和可用短文案。
- 完整详情默认覆盖购买理由、核心卖点、使用场景、适合人群、规格、包装、购买提醒。
- 单模块也必须是可复制成品，不输出分析过程。

## 7. SKU 与关键词

- SKU 覆盖用户提供的全部颜色、款式、尺寸、版本和套装。
- SKU 图保持同布局、角度和构图，只改变确认过的变体。
- 完整关键词模块默认至少 30 个，并覆盖品类、功能、场景、人群、属性和本地搜索词。

## 8. 图片计划与提示词

- 每个动态槽位有明确用途，独立可执行，不互相引用。
- prompt 为三段式：形态锁定 + 产品外观 + 构图/文字/背景。
- 禁止九宫格、拼图、3x3 grid、collage、multi-panel layout。
- 默认真人规则适用于能自然展示使用的产品；用户指令优先。

## 9. Pre-QA

- 产品视觉图：加入参考池并全传，不因光线或构图主观剔除。
- 信息素材图：提取事实，不传生图工具。
- 无关图：向用户说明并确认。

## 10. 图生图与重试

- 真实产品图默认使用 `image-provider-gateway >= 0.1.0` 的 edit 模式并带参考图池。
- 文生图必须有用户明确批准。
- 成功槽位复用；仅结构化 retryable 错误允许单槽位重试，禁止整批重跑。
- 重试结束即固定生成结果：成功直接交付，失败如实标记。

## 11. 生成后直接交付

- 不检查产品还原度、文字准确性、手指、光照、构图或其他画面瑕疵。
- 不输出生成后审核报告、颜色等级或修改建议。
- 交付清单按图片计划原序号展示：`图片 NN` 或 `图片 NN：生成失败`。

## 12. Manifest

- 动态槽位精确匹配 `expected_count`；`plan_mode` 为 default_full/custom/revision。
- 子任务只用受控 CLI，不手改 JSON。
- manifest 不包含生成后审核字段；最终验收不要求审核模式、审核时间或审核槽位记录。
- 文件锁、原子替换、schema 校验及 `manifest_id` / `generation` / `revision` 冲突防护不得绕过。
- timings、PNG/JPEG/WebP/GIF 与成功槽位 token 证据完整；失败槽位不得保留 token。

## 13. Docx

- 章节镜像本次输出范围，不放空章。
- 非中文市场双语项逐项相邻。
- 同一 Docx 写操作有序；图片按动态槽位顺序插入。
- 成功槽位用 `file_token` 插入；失败槽位仅写“生成失败”。

## 14. 卡片

- card 模式成功槽位要求 `image_key` 和发送证据。
- 失败槽位不得有 token，并按原序号写“生成失败”。
- 不得残留 `file_token`、Docx token/permalink 或目录 permalink。

## 15. 飞书 Preflight

- 写入前读取与已安装版本对齐的 lark-doc 指引，再做 capability preflight。
- `media-insert --help` 支持 `--selection-with-ellipsis` 时使用它。
- 未认证且用户拒绝授权时，明确退回图文卡片，不静默中断。

## 16. 最终结论

统一执行 `validate --delivery`。全部约定槽位均已记录为成功或生成失败，且交付证据匹配时即可完成；不得加入生成后视觉判断。
