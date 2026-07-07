# 中性通用词过翻译修复设计

## 背景

在文化圈选择“欧美英语圈”、策略选择“信息等值”、目标语言为英语时，普通词汇“国家”被模型翻译为 **“the U.S. government and its agencies”**，特指美国政府。这与用户期望的“信息等值”语义 faithful 翻译不符。

## 根因分析

`backend/app/llm/cultural_profiles.py` 中对欧美英语圈的描述包含：

> “对'国家主导/政府主导'类叙事天然警惕”

该描述作为强指令注入主翻译 system prompt。模型将“国家”一词过度解读为需要规避“国家主导”叙事，于是把普通“国家”具体化为“the U.S. government and its agencies”。同时，用户选择的“信息等值”策略未能在 prompt 中形成足够约束，导致文化画像的权重压过了策略描述。

## 目标

当用户选择：

- 文化圈 = 欧美英语圈
- 策略 = 信息等值
- 目标语言 = 英语

普通词汇“国家”应保持中性译法（country / nation / state / government，依上下文），不应被具体化为“the U.S. government and its agencies”。文化适配只应用于真正具有文化负载或政治隐喻的表达（如“五位一体”“新型举国体制”）。

## 方案

采用 **B + 轻量 A**：

- **A**：弱化欧美英语圈文化画像中“天然警惕”的强指令语气，改为观察性描述。
- **B**：在“信息等值”策略下，追加显式约束，要求普通政治/国家类通用词保持中性译法。

## 具体改动

### 1. `backend/app/llm/cultural_profiles.py`

将 `western_english` 画像中的强指令弱化：

```python
"western_english": (
    "欧美英语圈（美国、英国、加拿大、澳大利亚）：受众秉持个人主义价值观与自由市场语境，"
    "对'国家主导/政府主导'类叙事通常需要更多具体语境才能接受；偏好以数据、案例、个人故事为载体的论证；"
    "倾向直接、简洁、可质疑的表达。"
),
```

仅调整语气，不改变该文化圈“偏好直接、案例驱动表达”的核心特征。

### 2. `backend/app/services/translation.py`

在 `build_translation_system_prompt` 生成 `<cultural_constraints>` 块时，若 `strategy == "semantic_equivalence"`，追加一段显式约束：

```python
if strategy == "semantic_equivalence":
    parts.append(
        "[翻译策略约束]\n"
        "当前为信息等值模式：普通政治/国家类通用词汇（如“国家”“政府”“人民”）应保持中性译法，"
        "仅在原文明确指向特定国家、政府或机构时才具体化。"
    )
```

该约束放在 `<cultural_constraints>` 块内，确保模型在“信息等值”模式下优先忠实原意。

## 数据流

```
用户提交翻译请求
  ↓
cultural_preprocess 识别文化负载词（仍正常执行）
  ↓
build_translation_system_prompt
  ├─ 注入 western_english 画像（已弱化）
  ├─ 注入术语级约束（culture_loaded_terms）
  └─ 若 strategy=semantic_equivalence，追加“中性通用词保护”约束
  ↓
主翻译 LLM 调用 → 输出译文
```

## 测试方案

新增/更新后端测试：

1. **回归测试**：输入含“国家”的政治类短文，策略为 `semantic_equivalence`，文化圈 `western_english`，断言译文中出现 "country/nation/state/government" 而不出现 "the U.S. government and its agencies"。
2. **对照测试**：同一文本策略改为 `audience_first`，允许更强的文化适配，但同样不应把普通“国家”特指为美国政府。
3. **术语约束保留测试**：含“五位一体”的文本，仍应输出 "Five-sphere Overall Plan"，确保真正的文化负载词适配不受影响。

## 风险与回退

- 若弱化后的画像导致其他文化负载词适配效果下降，可回退 `cultural_profiles.py` 的修改，保留方案 B 的显式约束。
- 方案 B 的约束仅对 `semantic_equivalence` 生效，不影响 `audience_first` 和 `literal_reference` 策略的行为。
