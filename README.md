# ecommerce-product-listing-skill

当前版本：v2.8.0

用于跨境电商上架文案、本地化内容、产品图计划、图生图生产、QA 与飞书交付。

## 文件

- `SKILL.md`：运行判断与关键红线。
- `QUALITY_GATE.md`：仅在自检、真实生图或交付时读取。
- `OUTPUT_TEMPLATE.md`：仅在需要具体产物格式时读取。
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

所有子任务通过 `set-facts`、`set-image-plan`、`add-replacement`、`put-module`、`update-slot`、`set-qa`、`set-token`、`set-delivery`、`finalize` 等子命令更新 manifest，不手改 JSON。

## v4 清单与短交付信任边界

旧 `schema v3` 运行清单需执行 `init --force` 重建为 v4；generation/revision 保持单调，新清单使用新 identity。短交付消息必须先由可信调用方验证。CLI 的本地 registry 仅以 `(provider, channel, message_id)` 防止本机重复消费，不证明渠道消息或用户身份；默认使用稳定 XDG state 路径，测试可通过 `RUN_MANIFEST_APPROVAL_REGISTRY` 或 `--approval-registry` 隔离。
