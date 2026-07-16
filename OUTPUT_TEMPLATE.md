# Ecommerce Product Listing Output Templates

只在需要对应产物时选用，不要求一次加载全部模板。

## 1. 图片计划确认

```text
图片计划（plan_mode: default_full | custom | revision）

| 槽位 | 图型/用途 | 核心卖点 | 是否真人 | 备注 |
|---|---|---|---|---|
| 01 |  |  |  |  |

总数：N 张（expected_count=N）
请一次确认以上清单与总数；确认后开始生产。
```

用户仅泛化要求做产品图时，使用 default_full 默认完整方案 9 张。SKU 图、指定卖点图、指定图型或返工按明确数量生成；数量不明时使用上表确认。

## 2. 本地化内容单元

非中文市场完整 Docx 默认每项紧邻展示：

```markdown
### <项目名>
<source_text：目标语言原文>

**中文对照：** <zh_reference>
```

机器数据：

```json
{
  "source_text": "目标语言原文",
  "zh_reference": "逐项紧邻中文对照",
  "render_text": "实际发布或图片渲染文字"
}
```

显式要求单语时省略中文展示；中文市场不重复。中文对照不得传入生图 prompt，图片 prompt 只读取 `render_text`。

## 3. 动态图片提示词

每个槽位独立填写，不使用“同上”：

```text
### 槽位 NN｜图片用途
[Reference-Fidelity Block]
- 参考图池全传；锁定产品形态、结构、颜色和标识。

[Product-Appearance Block]
- 产品：
- 已确认变体：
- 材质/结构事实：

[Composition Block]
- 是否包含真人：
- 构图与背景：
- render_text 主标题：
- render_text 副标题：
- render_text 卖点标签：
- Negative rules：禁止九宫格、拼图、3x3 grid、collage、multi-panel layout。
```

多 SKU 可增加 Variant-Preservation Block，不作硬门槛。

## 4. Manifest 命令

先 init。旧 `schema v3` 运行清单不能直接 mutation/validate，必须用 `init --force` 重建为 v4；重建保留 generation/revision 单调递增，但会生成新的 manifest identity。

```bash
python3 scripts/run_manifest.py init run-manifest.json --task-scope content --target-language fr
python3 scripts/run_manifest.py init run-manifest.json --task-scope image --plan-mode default_full --delivery-mode docx
python3 scripts/run_manifest.py init run-manifest.json --plan-mode custom --expected-count 3 --confirmed-by-user
python3 scripts/run_manifest.py init run-manifest.json --force --task-scope image --plan-mode default_full
```

所有 mutation 都必须携带同一次读取所得的完整 identity。以下 shell helper 在**每次 mutation 前**读取当前 `manifest_id` / `generation` / `revision`，所以示例可直接执行；每次成功 mutation 会令 revision 递增，下一次调用会自动读取新 revision。

```bash
manifest_mutate() {
  command="$1"; manifest="$2"; shift 2
  eval "$(python3 - "$manifest" <<'PY'
import json, shlex, sys
m=json.load(open(sys.argv[1], encoding="utf-8"))
print("MID="+shlex.quote(m["manifest_id"]))
print("GEN="+shlex.quote(str(m["generation"])))
print("REV="+shlex.quote(str(m["revision"])))
PY
)"
  python3 scripts/run_manifest.py "$command" "$manifest" "$@" \
    --manifest-id "$MID" --generation "$GEN" --revision "$REV"
}

manifest_mutate set-facts run-manifest.json --json '{"market":"TH"}'
manifest_mutate set-image-plan run-manifest.json --json '[{"slot":1,"purpose":"hero"}]'
manifest_mutate put-module run-manifest.json title --module-kind internal --json '{"note":"draft"}'
manifest_mutate update-slot run-manifest.json 1 --json '{"status":"failed"}'
manifest_mutate set-qa run-manifest.json --json '{"mode":"9-image-single-round","reviewed_at":null,"reviewed_slot_ids":[],"reviewed_count":0}'
manifest_mutate set-token run-manifest.json 1 --json '{"image_key":"image_fixture"}'
manifest_mutate set-delivery run-manifest.json --json '{"deliverable_slots":[]}'
manifest_mutate timing run-manifest.json wave_0 --seconds 1.0
manifest_mutate add-replacement-slot run-manifest.json --replaces-slot 1 --purpose "替代槽位用途"
```

`put-module --from-current` 和 `timing --from-current` 只允许创建不存在的字段；同名模块或同 stage timing 拒绝盲覆盖。

短交付只有可信调用方验证渠道消息真实性与用户身份后才录入。审批原文必须以数字边界精确包含当前 `N->M`。本地 registry 只保证同一 `(provider, channel, message_id)` 在本机唯一消费，不证明外部消息真实性；默认路径稳定在 XDG state 目录，测试/隔离运行可用 `RUN_MANIFEST_APPROVAL_REGISTRY` 或 `--approval-registry` 指定。

```bash
export RUN_MANIFEST_APPROVAL_REGISTRY="$PWD/.test-short-approval-registry.json"
manifest_mutate set-short-delivery-approval run-manifest.json \
  --provider feishu --channel direct --message-id om_123456 --author-id ou_123456 \
  --approval-text "用户明确批准当前 9->8 短交付合同" \
  --captured-at 2026-07-16T09:00:00+08:00 --approved-count 8
manifest_mutate finalize run-manifest.json
python3 scripts/run_manifest.py validate run-manifest.json --delivery
```

## 5. 流水线摘要

```text
- 单一事实源：run-manifest.json
- 计划：<plan_mode>；验收：<actual>/<expected_count>（N/N）
- Wave 0：Pre-QA、能力预检、合并确认关口
- Wave 1：内容模块与三段式 prompt
- Wave 2：图生图、单槽位重试、single-round Post-QA、交付
- 增量恢复：成功槽位复用，禁止整批重跑
- QA：默认 9 图为九图单轮批审；🔴 候选二次复核
- Docx：同一 Docx 写操作有序
```

## 6. Post-QA

```markdown
## Post-QA

- 🟢：<槽位列表>
- 🟡：<槽位列表>
- 🔴 hard reject：<槽位 + 原因 + 替代槽位>
- 交付结果：N/N
- structured short-delivery approval：无 | <已绑定当前 N→M 合同的 evidence digest>

逐槽位：
- NN｜🟢/🟡/🔴｜观察｜修复建议：重出 / PS 后处理 / 遮盖裁剪 / 直接使用
```

hard reject 必须补齐替代槽位；未补齐时不能把 N-1/N 当完成。

## 7. Docx / 图文卡片分流

- **docx**：完整成品默认 Docx；每个可交付图记录 `file_token` + `image_key`，并记录 Docx、目录、卡片证据。
- **card**：只发卡片；只记录 `image_key`，不得残留 `file_token`、Docx 或目录证据。
- 飞书操作前先做版本对齐读取与 capability preflight；支持时使用 `--selection-with-ellipsis`。

Docx 链接消息：

```text
📄 完整版：<docx-permalink>
📁 产品文件夹：<folder-permalink>
🖼 图文卡片：已发送
```
