# ecommerce-product-listing-skill

当前版本：v2.9.0

用于跨境电商上架文案、本地化内容、产品图计划、图生图生产与飞书交付。

图片流程保留生图前 Pre-QA；图片生成后不做视觉质量审核或质量评级。生成成功按序号直接交付，生成失败按原序号如实标记。

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
