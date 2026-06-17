# 审校服务（Review Service）设计文档

**版本:** v1.0  
**日期:** 2026-06-17  
**对应 plan:** `docs/superpowers/plans/2026-06-17-review-service.md`  

---

## 1. 概述

审校服务是 CulturalBridge 的**事后诊断**模块，与现有的**事前翻译**工作台形成互补。用户可上传已发布的外宣作品（中文原文+外文译文，或仅外文译文），系统将对照检查翻译质量、文化适配和传播效果，输出内联标注、问题卡片和结构化审校报告。

---

## 2. 目标用户与场景

- **画像 A（国际传播编辑）**: 媒体已发布的多语言内容需要事后质量审计
- **画像 B（智库研究员）**: 已发表的政策解读译文需要传播效果诊断
- **画像 C（跨国企业本地化负责人）**: 品牌内容的各语言版本需要一致性检查

---

## 3. 核心功能

### 3.1 双模式输入

| 模式 | 输入 | 诊断能力 |
|------|------|---------|
| **对照审校** (dual) | 中文原文 + 外文译文 | 术语一致性、语义漂移、文化适配遗漏、叙事逻辑偏差 |
| **独立诊断** (single) | 仅外文译文 | 受众接受度、表达清晰度、传播效果优化、文化风险 |

### 3.2 四维审校体系

| 维度 | 说明 |
|------|------|
| **术语准确性** | 政治话语专有术语、政策固定译法；是否缺少必要注释 |
| **文化适配** | 译文在目标受众文化中是否产生负面联想或误读 |
| **表达清晰度** | 歧义、术语堆砌、过度直译、句子过长、逻辑跳跃 |
| **叙事逻辑** | 段落结构、因果链、论证顺序是否与原文一致（允许微调） |

### 3.3 输出形式（两者结合）

1. **内联标注**: 译文中彩色高亮标记问题处，hover 显示摘要
2. **问题卡片**: 右侧分类列出所有问题，支持双向联动高亮
3. **审校报告**: 底部可折叠面板，支持导出 PDF/Word

---

## 4. 架构设计

### 4.1 整体流程

```
用户进入 /review 页面
        |
        v
选择模式（dual / single）+ 输入内容 + 参数
        |
        v
POST /api/reviews
        |
        v
ReviewService
        |
        +-- dual_review(source, translated, params)
        |       |
        |       v
        |   DUAL_REVIEW_PROMPT -> LLM
        |
        +-- single_review(translated, params)
                |
                v
            SINGLE_REVIEW_PROMPT -> LLM
        |
        v
    解析 JSON -> ReviewResult
        |
        v
    返回前端 -> 内联标注 + 问题卡片 + 报告面板
```

### 4.2 复用策略

**复用现有能力：**
- 文化预处理服务 (`cultural_preprocess`)：目标受众画像分析
- 文体识别：沿用 genre 参数
- 风险标注样式系统：内联 mark 高亮 + 颜色分级

**新增专用层：**
- `ReviewService`：prompt 组装、LLM 调用、结果解析
- 审校专用 prompt 模板：针对"已发布内容诊断"优化

### 4.3 关键设计决策

1. **审校结果不持久化**（MVP）：直接返回前端，未来如需历史记录再扩展
2. **评分由 LLM 生成**（0-100），而非训练专用分类器（成本/时间权衡）
3. **双模式/单模式输出结构统一**（`ReviewResult`），前端渲染逻辑复用
4. **Span 定位基于字符偏移**：前端用 `String.slice()` 做内联高亮

---

## 5. 数据模型

```python
class ReviewIssue(BaseModel):
    category: str                 # "terminology", "cultural", "clarity", "narrative"
    severity: str                 # "low", "medium", "high"
    span: dict | None             # {"start": int, "end": int, "text": str}
    original: str                 # 译文中需要修改的片段
    suggestion: str               # 修改建议
    explanation: str              # 为什么需要修改（中文）
    source_reference: str | None  # 双模式时对应的中文原文

class ReviewCategory(BaseModel):
    name: str                     # "术语准确性", "文化适配", "表达清晰度", "叙事逻辑"
    score: int                    # 0-100
    issue_count: int
    issues: list[ReviewIssue]

class ReviewResult(BaseModel):
    review_id: UUID
    mode: str                     # "dual" | "single"
    overall_score: int            # 0-100
    target_language: str
    audience_baseline: str
    categories: list[ReviewCategory]
    summary: str                  # 中文摘要（100字以内）
    created_at: datetime
```

### 5.1 评分等级

| 分数 | 等级 | 颜色 |
|------|------|------|
| 90-100 | 优秀 | #22C55E |
| 75-89 | 良好 | #3B82F6 |
| 60-74 | 一般 | #EAB308 |
| 40-59 | 待改进 | #EA580C |
| 0-39 | 需重写 | #DC2626 |

---

## 6. API 设计

### 6.1 POST /api/reviews

**Request:**
```json
{
  "mode": "dual",
  "source_text": "在过去五年中，我们坚持以人民为中心的发展思想...",
  "translated_text": "Over the past five years, we have upheld a people-centered development philosophy...",
  "target_language": "en-GB",
  "genre": "political",
  "cultural_sphere": "western_english",
  "audience_type": "government"
}
```

**Response:** `ReviewResult`（见数据模型）

**Validation:**
- `mode` 为 "dual" 时，`source_text` 必填
- `mode` 为 "single" 时，`source_text` 可选（传了也不使用）
- `translated_text` 始终必填，长度限制 10000 字符

---

## 7. Prompt 设计

### 7.1 DUAL_REVIEW_PROMPT

```
你是一位资深国际传播审校专家。请对照下面的中文原文和外文译文，从以下四个维度进行审校分析，指出译文中的问题并给出修改建议。

审校维度：
1. 术语准确性：政治话语专有术语、政策文件固定译法是否准确、是否缺少必要的注释
2. 文化适配：译文表达在目标受众文化中是否会产生负面联想或误读
3. 表达清晰度：是否存在歧义、术语堆砌、过度直译导致难以理解
4. 叙事逻辑：段落结构、因果链、论证顺序是否与原文一致（允许因受众偏好微调，但需标注）

输出要求：
- 以 JSON 格式返回
- overall_score：总体评分（0-100）
- summary：一段中文摘要（100字以内），概括主要问题和建议
- categories：按四个维度分类，每个维度包含 score（0-100）和 issues 列表
- 每个 issue 必须包含：
  - category：分类标识（terminology / cultural / clarity / narrative）
  - severity："low"、"medium"、"high"
  - span：{"start": 字符偏移, "end": 字符偏移, "text": "译文中的对应文本"}
  - original：译文中需要修改的原文片段
  - suggestion：修改建议
  - explanation：为什么需要修改（中文，50字以内）
  - source_reference：对应的中文原文片段（如有）

原文中文：
{source_text}

译文（{target_language}）：
{translated_text}

目标受众：{audience}（{cultural_sphere}文化圈）

只返回 JSON，不要包含其他文本。
```

### 7.2 SINGLE_REVIEW_PROMPT

```
你是一位资深国际传播审校专家。请对下面的外文译文进行独立诊断，假设该译文已经发布给目标受众，请评估其传播效果和潜在风险。

诊断维度：
1. 受众接受度：目标受众是否会产生误读、负面联想或认知偏差
2. 表达清晰度：是否存在歧义、术语滥用、句子过长、逻辑跳跃
3. 传播效果优化：如何调整表达以提升说服力和可读性
4. 文化风险：哪些表达在目标文化中是高风险的，建议如何规避

输出要求：
- 以 JSON 格式返回，结构与双模式相同
- 单模式时 source_reference 字段可为 null
- overall_score：总体评分（0-100），基于受众接受度和表达清晰度综合评估

译文（{target_language}）：
{translated_text}

目标受众：{audience}（{cultural_sphere}文化圈）

只返回 JSON，不要包含其他文本。
```

---

## 8. 前端设计

### 8.1 页面结构

**路由：** `/review`（独立页面）  
**导航入口：** 顶部导航栏新增「审校」标签，与「工作台」并列

```
+==============================================================+
|  [≡ CulturalBridge]  [工作台] [审校] [术语库] [历史记录]     |
+==============================================================+
|                                                              |
|  +------------------------+  +---------------------------+   |
|  |  输入面板（左侧 ~42%）  |  |  审校结果（右侧 ~52%）     |   |
|  |                        |  |                           |   |
|  |  [模式选择]             |  |  [审校概览评分卡片]       |   |
|  |  ○ 对照审校             |  |  总分 + 四维度雷达/条形图  |   |
|  |  ● 独立诊断             |  |                           |   |
|  |                        |  |  [内联标注译文区]           |   |
|  |  [原文输入区]           |  |  带彩色高亮 + hover提示    |   |
|  |  [译文输入区]           |  |                           |   |
|  |                        |  |  [问题卡片列表]             |   |
|  |  [参数选择器]           |  |  分类可折叠 + 双向联动      |   |
|  |                        |  |                           |   |
|  |  [▶ 开始审校]           |  |  [导出报告 ▾]             |   |
|  +------------------------+  +---------------------------+   |
|                                                              |
|  +----------------------------------------------------------+|
|  |  审校报告面板（可折叠，默认展开）                          ||
|  |  结构化报告摘要 + 关键建议 + 导出按钮（PDF/Word）          ||
|  +----------------------------------------------------------+|
+==============================================================+
```

### 8.2 输入面板组件

**`review-input-panel.tsx`** 包含：
- 模式切换（radio group）：对照审校 / 独立诊断
- 原文输入区（textarea）：双模式时显示，单模式时隐藏（`display: none` 保留布局稳定）
- 译文输入区（textarea）：始终显示
- 参数选择器：目标语言、文体、文化圈（可选）、受众（可选）
- 开始审校按钮 + 加载状态

### 8.3 结果面板组件

**`review-result-panel.tsx`** 包含：
- **概览评分卡片**：总分大数字 + 进度条 + 四维度条形图
- **内联标注译文区**：复用 `TranslationResult` 的内联 mark 渲染逻辑，颜色按 category 分级
- **问题卡片列表**：复用 `RiskDetailCard` 的交互模式（hover 高亮、click 滚动定位）

**`issue-card.tsx`** 单条问题卡片：
- 左上角分类标签（彩色）+ 严重级别图标（🔴🟠🟡）
- 原文片段 + 修改建议（对比显示）
- 解释说明（折叠/展开）
- 「已处理」/「忽略」按钮（本地状态，不持久化）

### 8.4 报告面板组件

**`review-report-panel.tsx`** 包含：
- 审校摘要（overall summary）
- 分类问题汇总表
- 关键修改建议 TOP 5
- 导出按钮：导出为 Markdown / PDF（MVP 仅 Markdown）

---

## 9. 状态管理

**`review-store.ts`**（Zustand）：

```typescript
interface ReviewState {
  // 输入
  mode: "dual" | "single";
  sourceText: string;
  translatedText: string;
  params: { language: string; genre: Genre; sphere?: string; audience?: string };

  // 结果
  result: ReviewResult | null;
  highlightedIssueIndex: number | null;
  processedIssues: Set<number>;   // 用户标记为"已处理"的问题索引
  ignoredIssues: Set<number>;     // 用户标记为"忽略"的问题索引

  // UI
  isLoading: boolean;
  error: string | null;

  // Actions
  setMode: (mode: "dual" | "single") => void;
  setSourceText: (text: string) => void;
  setTranslatedText: (text: string) => void;
  setParams: (params: Partial<ReviewState["params"]>) => void;
  submitReview: () => Promise<void>;
  setHighlightedIssue: (index: number | null) => void;
  markProcessed: (index: number) => void;
  markIgnored: (index: number) => void;
  reset: () => void;
}
```

---

## 10. 后端文件结构

| 文件 | 动作 | 责任 |
|---|---|---|
| `backend/app/api/reviews.py` | 创建 | FastAPI router，POST /api/reviews |
| `backend/app/schemas/review.py` | 创建 | Pydantic schemas: ReviewRequest, ReviewResult, ReviewIssue, ReviewCategory |
| `backend/app/services/review.py` | 创建 | ReviewService: prompt 组装、LLM 调用、JSON 解析、异常处理 |
| `backend/app/llm/prompts.py` | 修改 | 追加 DUAL_REVIEW_PROMPT、SINGLE_REVIEW_PROMPT |
| `backend/app/main.py` | 修改 | 注册 reviews router |
| `frontend/app/(main)/review/page.tsx` | 创建 | 审校页面路由 |
| `frontend/components/review/review-input-panel.tsx` | 创建 | 输入面板 |
| `frontend/components/review/review-result-panel.tsx` | 创建 | 结果面板 |
| `frontend/components/review/review-report-panel.tsx` | 创建 | 报告面板 |
| `frontend/components/review/issue-card.tsx` | 创建 | 问题卡片 |
| `frontend/components/review/score-badge.tsx` | 创建 | 评分徽章 |
| `frontend/stores/review-store.ts` | 创建 | 审校状态管理 |
| `frontend/lib/api-client.ts` | 修改 | 新增 `postReview` 方法 |

---

## 11. 依赖与约束

### 11.1 依赖

- **后端**: 复用现有 `bailian_client`、`cultural_preprocess`（可选）
- **前端**: 复用现有 `Popover`、`Badge`、mark 渲染模式、Zustand store 模式
- **无新增外部依赖**

### 11.2 约束

- `translated_text` 最大 10000 字符（与翻译输入限制一致）
- 单次审校 LLM 调用约 5-15 秒（取决于文本长度），前端需显示加载状态
- LLM 返回的 JSON 可能包含幻觉 span，前端需做防御性校验（`indexOf` fallback）
- MVP 阶段审校结果不持久化，刷新页面丢失

---

## 12. 验收标准

- [ ] 导航栏出现「审校」入口，点击进入独立审校页面
- [ ] 支持「对照审校」和「独立诊断」两种模式切换
- [ ] 对照审校模式下输入原文+译文，输出四维审校分析
- [ ] 独立诊断模式下输入译文，输出受众接受度和传播效果诊断
- [ ] 审校结果包含：总体评分、分类评分、内联标注、问题卡片、审校报告
- [ ] 问题卡片支持 hover/click 双向联动高亮内联标注
- [ ] 审校报告面板可折叠，支持导出 Markdown
- [ ] 前端 TypeScript 编译通过，无错误
- [ ] 后端 API 返回正确的 JSON 结构，异常时返回友好错误信息
