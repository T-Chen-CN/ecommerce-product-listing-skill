# Ecommerce Product Listing Output Templates

只在需要对应产物时选用。

## 1. 图片计划确认

```text
图片计划（plan_mode: default_full | custom | revision）

| 槽位 | 图型/用途 | 核心卖点 | 是否真人 | 备注 |
|---|---|---|---|---|
| 01 |  |  |  |  |

总数：N 张（expected_count=N）
请一次确认以上清单与总数；确认后开始生产。
```

泛化产品图请求使用 default_full 默认完整方案 9 张；SKU 图、指定卖点图、指定图型或返工按明确数量生成。

## 2. 本地化内容单元

```markdown
### <项目名>
<source_text：目标语言原文>

**中文对照：** <zh_reference>
```

```json
{
  "source_text": "目标语言原文",
  "zh_reference": "逐项紧邻中文对照",
  "render_text": "实际发布或图片渲染文字"
}
```

显式要求单语时省略中文展示；中文市场不重复。中文对照不得传入生图 prompt。

## 3. 动态图片提示词

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

旧 schema 清单不能直接 mutation/validate，必须用 `init --force` 重建为当前 schema。

```bash
python3 scripts/run_manifest.py init run-manifest.json --task-scope content --target-language fr
python3 scripts/run_manifest.py init run-manifest.json --task-scope image --plan-mode default_full --delivery-mode docx
python3 scripts/run_manifest.py init run-manifest.json --plan-mode custom --expected-count 3 --confirmed-by-user
```

所有 mutation 携带同一次读取所得的完整 identity：

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
manifest_mutate update-slot run-manifest.json 1 --json '{"status":"success","file":"image-01.png"}'
manifest_mutate update-slot run-manifest.json 2 --json '{"status":"failed","provider_error":{"code":"timeout","message":"生成失败"}}'
manifest_mutate set-token run-manifest.json 1 --json '{"image_key":"image_fixture","file_token":"file_fixture"}'
manifest_mutate set-delivery run-manifest.json --json '{"deliverable_slots":[1],"failed_slots":[2]}'
manifest_mutate timing run-manifest.json wave_0 --seconds 1.0
manifest_mutate finalize run-manifest.json
python3 scripts/run_manifest.py validate run-manifest.json --delivery
```

## 5. 流水线摘要

```text
- 单一事实源：run-manifest.json
- 计划：<plan_mode>；槽位总数：<expected_count>
- Wave 0：Pre-QA、能力预检、合并确认关口
- Wave 1：内容模块与三段式 prompt
- Wave 2：图生图、单槽位重试、按序号直接交付
- 增量恢复：成功槽位复用，禁止整批重跑
- 结果：生成成功直接交付；生成失败如实标记
- Docx：同一 Docx 写操作有序
```

## 6. 图片交付清单

```markdown
## 图片交付

- 图片 01
- 图片 02
- 图片 03：生成失败
```

成功图片按序号附图或插入文档；失败序号只写“生成失败”，不附原因分析、质量评级或修改建议。

## 7. Docx / 图文卡片分流

- **docx**：成功图片记录 `file_token` + `image_key`；失败槽位不记录 token。
- **card**：成功图片只记录 `image_key`；失败槽位不记录 token；不得残留 Docx 证据。
- 飞书操作前先做版本对齐读取与 capability preflight。

```text
📄 完整版：<docx-permalink>
📁 产品文件夹：<folder-permalink>
🖼 图文卡片：已发送
```
