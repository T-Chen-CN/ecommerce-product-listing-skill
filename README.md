# 跨境电商产品上架与本地化内容生产 Skill

这是一个可复用的 Agent Skill，用于根据产品信息、产品图片、目标国家和销售平台，生成适合直接投入运营使用的跨境电商上架内容。

当前版本：**v2.2.0 Image-Edit-Only + Integrated Feishu Delivery**

## 适用场景

适用于：

- TikTok Shop / Shopee / Lazada / Amazon / Temu / Shopify 等平台
- 数码、家居、小家电、美妆个护、服饰配件、日用百货、母婴玩具等消费类产品
- 标题、卖点、详情、SKU、关键词、规格、包装清单、风险提醒、主图提示词、SKU 图提示词、9 张产品图提示词等内容生产场景

## v2.1 核心优化

### 1. 从“默认完整输出”升级为“模块化按需输出”

v2.1 引入 Modular Output Router：

- 默认按需输出
- 用户要什么，只输出什么
- 用户要求多个模块，只输出点名模块
- 只有明确要求“完整上架内容”时才全量输出
- 返工时只重写用户指出的模块

目标是解决 Agent 每次调用都一次性输出全部内容、内容太长、不方便分阶段生产的问题。

### 2. 完整模式仍然保留

如果用户明确要求完整上架内容，仍然会输出固定 10 个板块：

1. 产品定位
2. 标题建议
3. 核心卖点
4. 详情文案
5. 9 图提示词
6. SKU 命名
7. 关键词
8. 规格参数
9. 包装清单
10. 风险提醒

完整模式仍然保留 v2.0 的质量门槛：标题不能过短、卖点不能空泛、详情不能缩水、9 图提示词必须独立完整。

### 3. 质量门槛改为 Scope-aware

v2.1 的质量检查不再默认检查 10 个板块，而是先判断用户本次要求的输出范围：

- 用户只要标题：只检查标题质量
- 用户只要详情：只检查详情文案质量
- 用户只要 9 图：只检查 9 图提示词质量
- 用户要求完整上架内容：才检查完整 10 个板块

这样可以避免“用户只要一个模块，Agent 却因为质量门槛自动补齐全部内容”。

### 4. 支持常用模块单独调用

本 Skill 支持单独或组合调用以下模块：

- 产品定位
- 标题建议
- 核心卖点
- 详情文案
- 9 图提示词
- SKU 命名
- 关键词
- 规格参数
- 包装清单
- 风险提醒
- 主图提示词
- SKU 图提示词
- 视频脚本
- 达人合作话术
- 本地化翻译
- 平台适配优化

## 文件说明

```text
ecommerce-product-listing-skill/
├── README.md
├── SKILL.md
├── QUALITY_GATE.md
├── OUTPUT_TEMPLATE.md
└── CHANGELOG.md
```

- `SKILL.md`：核心 Skill 规则与输出路由
- `QUALITY_GATE.md`：按需模式、组合模式、完整模式的质量门槛
- `OUTPUT_TEMPLATE.md`：完整上架模式与模块化输出模板
- `CHANGELOG.md`：版本迭代记录

## 推荐调用语句

### 只产出标题

```text
按照 ecommerce-product-listing-skill，只产出标题建议。
目标国家：马来西亚
平台：TikTok Shop / Shopee / Lazada
产品信息如下：
……
```

### 只产出详情文案

```text
按照 ecommerce-product-listing-skill，只产出详情文案。
目标国家：马来西亚
平台：TikTok Shop / Shopee / Lazada
产品信息如下：
……
```

### 只产出 9 图提示词

```text
按照 ecommerce-product-listing-skill，只产出 9 张独立正方形产品图提示词。
目标国家：马来西亚
平台：TikTok Shop / Shopee / Lazada
产品信息如下：
……
```

### 只产出 SKU 命名

```text
按照 ecommerce-product-listing-skill，只产出 SKU 命名。
颜色 / 款式如下：
……
```

### 只产出 SKU 图提示词

```text
按照 ecommerce-product-listing-skill，只产出 SKU 图提示词。
要求每个颜色 1 张，布局一致，只改变颜色。
颜色如下：
……
```

### 组合输出

```text
按照 ecommerce-product-listing-skill，只产出：标题建议、详情文案、9 图提示词。
目标国家：马来西亚
平台：TikTok Shop / Shopee / Lazada
产品信息如下：
……
```

### 完整输出

```text
按照 ecommerce-product-listing-skill，输出完整上架内容。
目标国家：马来西亚
平台：TikTok Shop / Shopee / Lazada
产品信息如下：
……
```

## 输出原则

- 默认按需输出，不默认全量输出
- 标题必须具有平台搜索标题的信息密度
- 详情文案必须是可直接上架的成品
- 9 图提示词必须具备电商信息图属性
- 所有提示词必须独立完整，不能互相引用
- 规则必须跨类目通用，不绑定单一产品类型
- 不得编写用户未提供的参数、等级、背书或绝对化承诺
