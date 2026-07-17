# v2.12 持久化飞书交付路由设计

## 目标与范围

本次只修复飞书正式交付路径：首次初始化、持久化复用、失败诊断及显式降级。暂不包含 image-only 电商创意策略。

## 核心原则

飞书正式交付路线不是模型或单次任务的自由选择项。首次初始化把已验证路线写入无凭据的 Skill 运行配置；后续任务直接解析该配置。只有配置缺失、损坏、版本不兼容、被标记失效或实际调用返回认证/权限/资源失效错误时，才进入诊断。任何路线降级必须得到用户针对当前任务的明确确认。

## 架构

新增 `scripts/delivery_config.py`，管理 schema v1 的运行时配置。配置默认位于调用者显式传入的位置，或 `ECOMMERCE_LISTING_DELIVERY_CONFIG` 指定路径；仓库不保存真实运行配置或凭据。它提供 `bootstrap`、`status`、`resolve`、`record-success`、`invalidate`，使用文件锁和原子替换。

`bootstrap` 接收已经由首次环境验证得出的非敏感结果，只允许正式路线 `docx` 或 `interactive_card`。在飞书 Docx 已配置环境中，默认记录 `docx`。脚本拒绝 token、secret、password、credential、api_key 等敏感字段。

`resolve` 输出唯一正式路线及来源。默认来源为 `skill_config`；仅携带用户确认文本的一次性覆盖可返回 `interactive_card`，来源为 `explicit_user_override`，且不修改持久化默认值。`preview_images` 不是正式路线。

## Manifest 合同

Manifest schema 升级为 v8。删除由模型自由决定的 `--delivery-mode docx|card`，初始化必须消费 `delivery_config.py resolve` 生成的受控 route JSON 文件。根字段记录：

- `delivery_route`: `docx|interactive_card`
- `delivery_route_source`: `skill_config|bootstrap_result|explicit_user_override`
- `delivery_config_schema_version`: `1`
- `delivery_override`: `null` 或包含用户确认文本、路线、记录时间

运行清单只记录路由解析结果，不负责选路。旧 schema 必须 `init --force` 重建。普通图片预览不能写入正式交付证据。

## Bootstrap 与日常运行

首次或配置异常时：验证 lark-cli、身份、Docx/云盘/插图能力，完成最小调用验证，再调用 `bootstrap` 持久化非敏感结果。

正常任务：`resolve` → 初始化 Manifest → 直接执行配置路线。不得重复全量 preflight，不得临时改路。

## 失败状态机

- 临时网络/服务错误：有限重试原路线，不降级。
- 认证/权限错误：停止并报告重新授权；恢复后继续原路线。
- 配置损坏/版本不兼容：重新 Bootstrap。
- Docx 确实不可用：向用户提供修复 Docx 或本次显式覆盖 Interactive Card；未经确认不得切换。
- 普通散图仅在用户明确要求预览/散图时发送，不构成正式交付。

## 文档规则

`SKILL.md`、`QUALITY_GATE.md`、`OUTPUT_TEMPLATE.md` 统一使用 `interactive_card`，并明确配置优先、失败才诊断、禁止静默降级。README 说明首次初始化和日常调用。CHANGELOG 记录 v2.12.0。

## 测试

新增配置生命周期测试：原子 bootstrap、并发、敏感字段拒绝、损坏/旧 schema、resolve、一次性覆盖、不修改默认配置、invalidate、record-success。更新 Manifest 测试，证明无 route 文件不能初始化、非法来源/路线被拒、旧自由选路参数不可用、Docx 和 Interactive Card 证据隔离、preview 不能冒充正式交付。全量 unittest、quick_validate、py_compile、git diff --check 必须通过。
