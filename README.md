# ecommerce-product-listing-skill

当前版本：v2.11.0

用于跨境电商上架文案、本地化内容、产品图计划、图生图生产与飞书交付。

图片流程保留生图前 Pre-QA；图片生成后不做视觉质量审核或质量分级。生成成功按序号直接交付，生成失败按原序号如实标记。

## 文件

- `SKILL.md`：运行判断与关键红线。
- `QUALITY_GATE.md`：最终结构、事实与交付证据检查。
- `OUTPUT_TEMPLATE.md`：具体产物格式。
- `scripts/run_manifest.py`：动态、并发安全的 manifest 受控 CLI。
- `CHANGELOG.md`：版本历史。
- `tests/`：契约与 CLI 测试。

## 快速验证

```bash
python3 -m unittest discover -s tests -v
python3 ~/.npm-global/lib/node_modules/openclaw/skills/skill-creator/scripts/quick_validate.py .
```

## Manifest 示例

```bash
# 泛化产品图请求：默认完整 9 图
python3 scripts/run_manifest.py init run.json --plan-mode default_full

# 已确认的 N 图定制任务
python3 scripts/run_manifest.py init run.json --plan-mode custom --expected-count N --confirmed-by-user

# 最终验收
python3 scripts/run_manifest.py validate run.json --delivery
```

所有子任务通过 `set-facts`、`set-image-plan`、`put-module`、`update-slot`、`set-token`、`set-delivery`、`timing`、`finalize` 等子命令更新 manifest，不手改 JSON。

## 当前清单合同

清单不包含生成后审核字段。成功槽位保留真实图片和交付 token；失败槽位记录 provider 错误并进入 `failed_slots`，不得拥有 token。旧 schema 运行清单需执行 `init --force` 重建。

## v2.11 目录与命名摘要

固定路径为 `/{agent_name}/电商需求/Listing/{slug}/`。`agent_name` 仅从 `IDENTITY.md` 的“名字”字段读取，缺失 hard fail，不用 `open_id` / `agent id` 兜底。Skill 以 `(parent_token, exact_name)` 为目录身份，在单机跨进程文件锁内完整分页列举直属子项：1 个精确匹配复用，0 个二次查后创建，>1 个阻断；创建后重新列举并验证唯一匹配且 token 等于创建返回 token。验证非空非占位 token、名称/type/parent，禁止 root fallback，JSON 捕获隔离 stderr。

slug 为品牌型号原样 + ISO 3166-1 alpha-2 大写国家码；同产品同市场跨天与返工复用。图片使用 `MainNNN-NN`（SKU 仅在用户明说时使用），Docx 使用 `YYYYMMDD-{slug}-NNN.docx`，两者独立批次。schema v7 记录 `agent_name`、`product_slug`、`market_country_code`、`drive_path_segments`、`delivery.directory_chain`（含 `resolution`、`exact_match_count_first/second/after`、`created`、`created_token`、`pages_scanned_first/second/after`、`resolved_at`）、`delivery.product_folder_token`、`delivery.folder.permalink`、`delivery.docx.docx_filename`、`delivery.docx.docx_batch`、`images[].asset_filename`、`images[].image_batch`。validate 拒绝空 token、占位 token、父子关系不一致、文件名不匹配，以及 reused/created 证据不一致。Docx 模式聊天只发链接；card 不伪造目录证据。
