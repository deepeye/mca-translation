# 叙事重排（受众优先策略）设计文档

> 目标：把文化适配从词句级扩展到篇章结构级。系统基于中文原文、当前译文、文体、目标文化圈和受众类型，生成“当前结构 vs 建议结构”的叙事重排建议；用户生成预览并确认后，才将轻度衔接润色后的重排译文应用到当前结果。

## 1. 背景与目标

当前 CulturalBridge 已具备文化感知翻译、风险标注、转译决策日志、术语高亮、审校服务和接受度评分。现有能力主要集中在词汇、句子、风险片段和评分维度；“受众优先策略”还缺少篇章结构层面的完整闭环。

中文国际传播文本常采用背景先行、政策语境先行、价值铺垫先行的叙事方式。部分目标受众更习惯先看到结论、影响、行动意义或新闻导语，再理解背景。叙事重排功能用于识别这种结构差异，给出可解释的重排建议，并在用户确认后生成可应用的重排版本。

本功能第一版采用 **建议 → 预览 → 确认应用**，避免系统自动改写正文，保留编辑最终控制权。

## 2. 范围

### 2.1 做什么

- 用户手动触发“分析叙事结构”。
- 当接受度评分偏低时，显示“建议分析叙事结构”的提示，但不自动调用 LLM。
- 后端基于中文原文、当前译文、文体、目标文化圈、受众类型生成结构分析。
- 前端展示“当前结构 vs 建议结构”的对照式结构卡片。
- 每条建议标注一个主因：受众阅读习惯、文化认知差异、传播效果。
- 用户点击“生成重排预览”后，系统生成轻度衔接润色版译文。
- 用户确认后，后端校验当前译文未过期并写回重排译文。
- 应用后清理或失效位置敏感状态，并触发全文接受度重算。
- 叙事分析、预览生成、应用动作写入决策日志。

### 2.2 不做什么

- 不在翻译完成后默认自动重写正文。
- 不做完整重译。
- 不新增专门的“叙事受众模板”管理后台。
- 不跨多个 translation job 聚合学习。
- 不改变现有风险词接受、忽略、回退工作流。
- 不把叙事重排嵌入核心翻译 pipeline。

## 3. 用户流程

1. 用户完成一次转译后，在译文区看到“叙事重排建议”入口。
2. 用户点击“分析叙事结构”。如果接受度评分低于阈值，系统额外显示提示，引导用户点击分析。
3. 后端读取当前 job 的原文、译文、文体、目标文化圈和受众类型，生成结构分析。
4. 前端展示两组结构：
   - 当前译文结构
   - 建议目标受众结构
5. 每条建议显示摘要、引用片段、建议顺序、主因标签、理由和预期效果。
6. 用户点击“生成重排预览”。
7. 后端根据建议结构生成轻度衔接润色后的预览译文。
8. 前端展示预览译文，用户可取消或应用。
9. 用户确认应用后，后端校验 text hash 未过期，写回译文结果。
10. 应用成功后，旧风险高亮、旧接受度评分和旧叙事建议失效；系统触发全文接受度重算。

## 4. 架构与模块边界

叙事重排作为独立编辑增强能力实现，复用现有 job、译文、文化参数和决策日志，但不成为每次翻译必须执行的 pipeline 步骤。

### 4.1 后端

新增：

```text
backend/app/services/narrative_reframe.py
backend/app/schemas/narrative_reframe.py
```

扩展：

```text
backend/app/api/jobs.py
backend/app/services/decision_log.py
```

后端服务包含三个核心能力：

1. **分析建议**
   - 输入：原文、当前译文、genre、culture_sphere、audience_type。
   - 输出：当前结构、建议结构、重排理由、主因标签、预期效果、置信度。
   - 不修改译文。

2. **生成预览**
   - 输入：当前译文、已生成分析结果、当前 text hash。
   - 输出：重排后的预览译文。
   - 允许轻度衔接润色，但不做完整重译。

3. **应用预览**
   - 输入：预览译文、分析结果、当前 text hash。
   - 校验译文未过期后写回 job result。
   - 清理或失效位置敏感状态。
   - 触发全文接受度重算入口。
   - 写入 narrative 决策日志。

### 4.2 前端

新增：

```text
frontend/components/workspace/narrative-reframe-panel.tsx
frontend/components/workspace/narrative-structure-card.tsx
frontend/components/workspace/narrative-reframe-preview.tsx
frontend/components/workspace/narrative-reason-badge.tsx
```

扩展：

```text
frontend/stores/translation-store.ts
frontend/lib/api-client.ts
frontend/components/workspace/output-panel.tsx
```

组件职责：

| 组件 | 职责 | 依赖 |
|---|---|---|
| `NarrativeReframePanel` | 整体流程：低分提示、分析入口、建议展示、预览生成、应用/取消 | `useTranslationStore` |
| `NarrativeStructureCard` | 展示当前结构与建议结构条目 | 纯 props |
| `NarrativeReframePreview` | 展示预览译文和确认/取消操作 | 纯 props + 回调 |
| `NarrativeReasonBadge` | 展示主因标签 | 纯 props |

前端异步逻辑放在 `translation-store`，组件不直接调 `apiClient`。`api-client` 只封装 HTTP 方法，不包含业务状态判断。

## 5. 数据结构

### 5.1 主因标签

固定三类，便于前端展示和后端校验：

```text
audience_habit     受众阅读习惯
cultural_context   文化认知差异
communication      传播效果
```

### 5.2 分析结果

```ts
type NarrativeReasonLabel =
  | "audience_habit"
  | "cultural_context"
  | "communication"

type NarrativeOutlineItem = {
  id: string
  order: number
  summary: string
  text_span: string
}

type NarrativeRecommendedItem = {
  id: string
  target_order: number
  source_ref_ids: string[]
  summary: string
  reason_label: NarrativeReasonLabel
  reason: string
  expected_effect: string
}

type NarrativeReframeAnalysis = {
  source_outline: NarrativeOutlineItem[]
  current_translation_outline: NarrativeOutlineItem[]
  recommended_outline: NarrativeRecommendedItem[]
  overall_rationale: string
  confidence: number
}
```

要求：

- `confidence` 范围为 `0..1`。
- `recommended_outline` 可以为空；为空表示无明显重排价值。
- `text_span` 用于帮助用户定位结构片段，不作为稳定 offset。
- `source_ref_ids` 引用当前译文结构条目，表示建议重排来源。

### 5.3 前端 store 状态

每个语言结果下新增：

```ts
type NarrativeReframeState = {
  analysis: NarrativeReframeAnalysis | null
  previewText: string | null
  isAnalyzing: boolean
  isPreviewing: boolean
  isApplying: boolean
  error: string | null
  lastAnalyzedTextHash: string | null
}
```

`lastAnalyzedTextHash` 用于判断当前译文是否已经变化。如果用户接受/回退风险词、重新翻译或手动应用其他修改，旧建议显示为“可能已过期”，并禁用应用操作。

## 6. API 设计

### 6.1 分析叙事结构

```http
POST /api/jobs/{job_id}/narrative-reframe/analyze
```

请求：

```json
{
  "lang": "en"
}
```

后端从 job result 中读取原文、当前译文、genre、culture_sphere、audience_type。

返回：

```json
{
  "analysis": {
    "source_outline": [],
    "current_translation_outline": [],
    "recommended_outline": [],
    "overall_rationale": "当前译文忠实保留中文背景先行结构，但对目标受众而言进入主题较慢。",
    "confidence": 0.82
  },
  "text_hash": "sha256-of-current-translation"
}
```

### 6.2 生成重排预览

```http
POST /api/jobs/{job_id}/narrative-reframe/preview
```

请求：

```json
{
  "lang": "en",
  "analysis": {},
  "text_hash": "sha256-of-current-translation",
  "mode": "light_cohesion"
}
```

返回：

```json
{
  "preview_text": "The initiative’s main value for local audiences is stated first, followed by the policy background and supporting context.",
  "text_hash": "sha256-of-current-translation"
}
```

`mode` 第一版只支持 `light_cohesion`，表示保留主体内容并允许少量过渡句或衔接词调整。

### 6.3 应用重排预览

```http
POST /api/jobs/{job_id}/narrative-reframe/apply
```

请求：

```json
{
  "lang": "en",
  "preview_text": "The initiative’s main value for local audiences is stated first, followed by the policy background and supporting context.",
  "analysis": {},
  "text_hash": "sha256-of-current-translation"
}
```

行为：

- 校验 job、语言结果和当前译文存在。
- 校验当前译文 hash 与请求 `text_hash` 一致。
- 写回该语言的 translated text。
- 清理或失效旧风险标注 offset、旧 highlighted risk、旧接受度评分、旧叙事建议。
- 触发全文接受度重算入口。
- 写入 narrative 决策日志。

返回：

```json
{
  "result": {},
  "text_hash": "sha256-of-updated-translation"
}
```

如果 hash 不匹配，返回 409，并提示“当前译文已变化，请重新分析叙事结构”。

## 7. 数据流

### 7.1 手动分析

```text
用户点击“分析叙事结构”
→ store.analyzeNarrativeReframe(lang)
→ POST /api/jobs/{id}/narrative-reframe/analyze
→ 后端读取 job 原文、当前译文、genre、culture_sphere、audience_type
→ narrative_reframe.py 调用 LLM 生成结构分析
→ 返回 analysis + text_hash
→ 前端展示“当前结构 vs 建议结构”对照卡片
```

### 7.2 接受度低分提示

```text
AcceptanceScorePanel 得到评分
→ 如果 total_score < 75，或 fluency < 18，或 style < 18
→ NarrativeReframePanel 显示提示：
  “当前译文可能存在受众叙事适配问题，可分析叙事结构”
→ 用户手动点击分析
```

阈值第一版固定，不引入后台配置。

### 7.3 生成预览

```text
用户点击“生成重排预览”
→ store.previewNarrativeReframe(lang)
→ POST /api/jobs/{id}/narrative-reframe/preview
→ 后端校验当前 text_hash
→ LLM 按 recommended_outline 生成轻度衔接润色版
→ 返回 preview_text
→ 前端展示预览区
```

### 7.4 确认应用

```text
用户点击“应用到译文”
→ store.applyNarrativeReframe(lang)
→ POST /api/jobs/{id}/narrative-reframe/apply
→ 后端校验 hash，写回该语言译文
→ 清理或失效位置敏感状态
→ 触发全文接受度重算
→ 写入 narrative 决策日志
→ 前端展示更新后的译文
```

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| LLM 分析失败 | 保留原译文，面板显示“分析失败，请稍后重试” |
| 预览生成失败 | 保留结构建议，允许重新生成预览 |
| hash 过期 | 禁用应用，提示“当前译文已变化，请重新分析叙事结构” |
| 低置信度 | 展示建议，但标注“建议仅供参考” |
| 无明显重排价值 | 显示“当前结构已较符合目标受众阅读习惯” |
| 应用失败 | 不替换前端译文，避免前后端状态不一致 |
| 缺少原文或译文 | 返回明确错误，不调用 LLM |

## 9. 与现有系统联动

### 9.1 接受度评分

- 低分时显示叙事分析提示。
- 应用重排后触发全文接受度重算，而不是 delta 重算。
- 重算期间可保留旧分并显示刷新状态，避免 UI 闪空。

### 9.2 风险标注

应用重排后译文结构和位置发生变化，旧风险 offset 不再可信。第一版采用保守策略：

- 清理当前语言的 highlighted risk。
- 旧风险标注标记为需要重新计算或从 UI 隐藏。
- 不沿用旧 offset 做高亮。

### 9.3 决策日志

新增 `narrative` 阶段，用于记录：

- 叙事结构分析的整体理由。
- 每条建议的主因标签和预期效果。
- 预览生成模式 `light_cohesion`。
- 用户应用重排的动作。

新增阶段优于复用 `suggestion`，因为叙事重排是篇章结构层面的编辑增强，不等同于词句替换建议。

### 9.4 翻译管线

叙事重排不进入默认翻译 pipeline。它读取翻译结果并作为后置编辑能力运行，降低成本和失败影响。

## 10. 测试策略

### 10.1 后端单测

- schema 校验：`reason_label` 枚举、`confidence` 范围、outline 字段必填。
- analyze endpoint：正常 job、缺少译文、缺少原文、无重排价值、LLM JSON 解析失败。
- preview endpoint：hash 匹配、hash 不匹配、空建议、低置信度建议。
- apply endpoint：hash 校验、写回译文、清理/失效旧状态、触发接受度重算入口、写入 narrative 决策日志。

### 10.2 前端单测

- `NarrativeReframePanel` 初始状态、loading、error、empty suggestions。
- 低分提示出现条件：`total_score < 75`、`fluency < 18`、`style < 18`。
- 当前结构/建议结构卡片渲染。
- 主因标签渲染。
- text hash 过期后应用按钮禁用。
- 生成预览后确认/取消行为。
- store actions 的 analyze、preview、apply 状态流转。

### 10.3 集成验证

- 完成一次翻译 → 手动分析 → 生成预览 → 应用 → 译文更新。
- 应用后接受度评分全文重算。
- 应用后旧风险高亮不再指向错误位置。
- 重新翻译或接受/回退风险词后，旧叙事建议显示过期。

## 11. 实施顺序建议

1. 后端 schema 与服务骨架。
2. analyze endpoint 与 LLM JSON 解析。
3. preview endpoint 与 `light_cohesion` prompt。
4. apply endpoint、hash 校验、状态清理和决策日志写入。
5. 前端 api-client 与 store 状态。
6. 结构对照卡片与主因标签。
7. 预览区与应用/取消流程。
8. 低分提示与 OutputPanel 集成。
9. 单测与集成验证。

## 12. 成功标准

- 用户可以在翻译完成后手动分析叙事结构。
- 系统能展示当前结构和目标受众建议结构的清晰对照。
- 每条建议都有明确主因标签、理由和预期效果。
- 用户可以生成轻度衔接润色的重排预览。
- 只有用户确认后，重排预览才会写回当前译文。
- 译文变化后旧建议不能被静默应用。
- 应用后接受度评分全文重算，旧位置高亮不产生误导。
