# 接受度评分前端 UI（Acceptance Scoring UI）设计文档

> P2 功能。工作台译文区右侧评分面板：总分 + 四维 + 置信度 + Top3 风险条目 + 受众基准切换。复用现有风险标注联动。后端 API 已完成（首次评分 + delta 重算）。

## 1. 背景与核心取舍

后端接受度评分（`docs/superpowers/specs/2026-07-01-acceptance-scoring-design.md`）已完成：`POST /api/jobs/{id}/acceptance-score`（首次/受众切换全文重算）+ `POST /api/jobs/{id}/acceptance-score/delta`（句级重算）。本设计做前端 UI。

**核心衔接断裂**：后端 delta 端点原签名 `{lang, sentence_id, new_text}`，但前端风险词 accept/revert 时手里只有 `risk_index`（+ phrase/suggestion/new translatedText），无 `sentence_id`；后端缓存的 `acceptance_sentence_scores`（SentenceScore）也不带 char_offset/text，前端无法把 risk_index 映射到 sentence_id。

**取舍（方案 A）**：后端 delta 端点改收 `{lang, risk_index}`。后端读 `risk_annotations[risk_index]`（accept/revert 路由已重算 offset）→ 重切 `result.translated_text` → 找包含 offset 的句 → 重算该句 + affects_neighbors 邻接句 → 聚合写回。前端只发天然就有的 `risk_index`，零映射逻辑；后端复用已有的重切逻辑，无句子边界 staleness 问题。代价：改「已完成」的后端 delta 端点签名 + 测试——属于本次前端工作暴露的集成错配修复。

## 2. 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 触发方式 | 全自动 | 转译完成自动首次评分；accept/revert 自动 delta。符合 PRD §4.2「转译完成即打分、替换后 delta<1s」即时反馈定位 |
| 受众基准切换器 | 做三选一按钮组 | PRD §4.2 把「受众基准可切」列为应对分类器偏见的核心策略；后端已支持；前端只差控件+一次重算 |
| delta 数据映射 | 后端 delta 改收 risk_index | 前端发天然数据、零映射；后端复用重切逻辑；无 staleness |
| 面板位置 | TranslationResult 与 RiskDetailList 之间 | 评分是译文派生反馈，紧跟译文、在风险详情之上 |
| accept-all 后 | 触发首次评分（全文重算） | 多句都改了，单句 delta 不够；accept-all 是批量操作，用户预期等待 |

## 3. 架构与组件

新增面板组件 + store slice + API 方法 + 后端端点签名调整。贴合现有 `OutputPanel` / `translation-store` / `apiClient` 模式。

```
frontend/
├── components/workspace/acceptance-score-panel.tsx      # 主面板（collapsible，仿 DecisionLogPanel）
├── components/workspace/acceptance-score-skeleton.tsx   # 加载骨架（仿 DecisionLogSkeleton）
├── components/workspace/acceptance-dimension-bar.tsx     # 四维条形（仿 review/CategoryScoreBar）
├── components/workspace/__tests__/acceptance-score-panel.test.tsx
├── components/workspace/__tests__/acceptance-dimension-bar.test.tsx
├── stores/__tests__/acceptance-store.test.ts             # store action 单测
├── stores/translation-store.ts                           # 扩展 LangResult + 新 actions
└── lib/api-client.ts                                     # 加 2 个方法
backend/
└── app/api/jobs.py                                       # delta 端点签名 sentence_id→risk_index
```

### 组件职责

| 组件 | 职责 | 依赖 |
|---|---|---|
| `AcceptanceScorePanel` | 面板外壳：collapsible 头（标题 + 受众基准切换器）、总分、四维条、置信度标注、Top3 风险条目、常驻「非审计级」小字。无业务逻辑，全读 store。 | `useTranslationStore` |
| `AcceptanceDimensionBar` | 单条四维可视化：标签 + 0–25 分条 + 数值。纯展示。 | 无（纯 props） |
| `AcceptanceScoreSkeleton` | 首次评分/受众切换 loading 的 3 行 pulse 骨架。 | 无 |
| Store actions | `triggerFirstScoring`、`triggerDeltaScoring`、`setAcceptanceScore`、`clearAcceptanceScore` | `apiClient` |
| API methods | `postAcceptanceScore`、`postAcceptanceScoreDelta` | `apiClient.post` |

### 与既有系统的边界

- 面板插入 `OutputPanel` flex 列，位于 `TranslationResult` 与 `RiskDetailList` 之间
- 复用 `DecisionLogPanel` 的 collapsible 模式（local `useState` + button toggle，不用 shadcn Collapsible——项目无此组件）
- Top3 风险条目点击 → 复用现有 `scroll-to-risk-mark` CustomEvent + `highlightedIndex` store，与 `<mark>` 联动（不造第二套高亮）
- 四维条用 inline div（仿 `review/score-badge.tsx` 的 `CategoryScoreBar`），不引入 shadcn Progress（项目无）
- 受众基准切换器用按钮组（3 个 Button，active 态 teal 背景），不引入 shadcn Select（项目无）
- 颜色：总分 teal `#0D9488`；四维条 teal 渐变；置信度低标灰 + terracotta `#C2410C` 提示；Top3 复用 `var(--color-risk-*)`

### 设计原则

`AcceptanceDimensionBar` 和 `Skeleton` 是纯展示，可单测不依赖 store；`AcceptanceScorePanel` 是唯一有业务逻辑的组件（读 store + dispatch scroll 事件）；store actions 封装所有异步+API，组件不直接调 `apiClient`（与现有 `loadDecisionLogs` 模式一致）。

## 4. 数据流

### 首次评分（转译完成自动触发）

```
pollJobStatus 检测 status === "completed"
        │
        ▼
AcceptanceScorePanel useEffect 监听 result.status === "completed" && acceptanceScore === -1
        │  （幂等：已评分或评分中不触发）
        ▼
store.triggerFirstScoring(lang, "policy_media")   ← 默认受众基准
        │
        ▼
apiClient.postAcceptanceScore(jobId, {lang, audience_baseline})
  → POST /api/jobs/{id}/acceptance-score
        │
        ▼
后端首次评分（并发切句评分）返回 {total_score, dimensions, confidence, top3_risk_indices, audience_baseline}
        │
        ▼
store.setAcceptanceScore(lang, payload)
  → 更新 LangResult: acceptanceScore, acceptanceDimensions, acceptanceConfidence,
    acceptanceTop3Risks, audienceBaseline, isScoringAcceptance=false
        │
        ▼
面板渲染：总分 + 四维条 + 置信度 + Top3 + 受众基准高亮
```

### Delta 重算（风险词 accept / revert 自动触发）

```
用户在 RiskDetailCard 点 accept（或 revert）
        │
        ▼
risk-detail-list.tsx 现有逻辑：调 accept API → store.acceptRisk() 更新译文+标注
        │  （译文已替换，risk_annotations[risk_index].status = accepted，offset 已重算）
        ▼
accept 成功后追加调用 store.triggerDeltaScoring(lang, risk_index)
        │
        ▼
apiClient.postAcceptanceScoreDelta(jobId, {lang, risk_index})
  → POST /api/jobs/{id}/acceptance-score/delta   ← 签名改为 {lang, risk_index}
        │
        ▼
后端 _run_acceptance_delta（改后）：
  读 risk_annotations[risk_index]（offset 已重算）→ 重切 result.translated_text
  → 找包含该 offset 的句 → score_sentence_single + affects_neighbors 邻接句
  → 聚合写回，返回新 {total_score, dimensions, confidence, top3_risk_indices, audience_baseline}
        │
        ▼
store.setAcceptanceScore(lang, payload)   ← 复用同一 setter
        │
        ▼
面板分数滚动更新（delta <500ms 无 spinner；>500ms 局部 AcceptanceScoreSkeleton）
```

### 受众基准切换（手动）

```
用户点面板头的受众基准按钮（如 academic）
        │
        ▼
store.triggerFirstScoring(lang, "academic")   ← 复用首次评分端点，带新基准
        │  （isScoringAcceptance=true，面板保留旧分不闪空，直到新分返回）
        ▼
POST /api/jobs/{id}/acceptance-score {lang, audience_baseline: "academic"}
        │
        ▼
后端全文重算（audience 变了，全文维度都变）返回新 payload
        │
        ▼
store.setAcceptanceScore(lang, payload)   ← 覆盖旧分
```

### 幂等与防抖

- 首次评分 effect 依赖 `[result.status, result.acceptanceScore]`，仅在 `completed && acceptanceScore === -1` 时触发；`isScoringAcceptance` 期间不再触发
- 单个 accept → 单次 delta；`accept-all` → 完成后触发一次首次评分（全文重算），避免并发 delta 互相覆盖缓存
- revert → 同 delta（revert 把句文改回原样，重算同句）

### 性能/UX 对照（PRD §8）

- 首次评分 p95 < 2s：`isScoringAcceptance` 期间显示骨架；译文已展示，评分是附加
- Delta p95 < 1s：局部骨架 >500ms 才显示（PRD 第 791 行）；<500ms 无感知
- 受众切换 2–3s：面板 loading，保留旧分不闪空

## 5. Store 状态与 API

扩展 `translation-store.ts` 的 `LangResult` + 新增 actions。贴合现有 `setResult` partial-merge 模式。

### `LangResult` 新增字段

```ts
interface LangResult {
  // ...既有...
  acceptanceScore: number;                  // 已有，-1 未评分
  // 新增：
  acceptanceDimensions?: DimensionScores;   // {audience, cultural, naturalness, risk} 各 0-25
  acceptanceConfidence?: number;            // 0-1
  acceptanceTop3Risks?: number[];           // risk_index 数组（引用 risk_annotations）
  audienceBaseline?: AudienceBaseline;      // 当前评分所用基准
  isScoringAcceptance?: boolean;            // 评分进行中（首次/delta/受众切换）
}

type AudienceBaseline = "policy_media" | "academic" | "social_media";
interface DimensionScores {
  audience: number; cultural: number; naturalness: number; risk: number;
}
```

### 新增 store actions

```ts
interface TranslationState {
  // ...既有...
  triggerFirstScoring: (lang: string, audienceBaseline: AudienceBaseline) => Promise<void>;
  triggerDeltaScoring: (lang: string, riskIndex: number) => Promise<void>;
  setAcceptanceScore: (lang: string, payload: AcceptanceScorePayload) => void;
  clearAcceptanceScore: (lang: string) => void;  // 转译新任务/切换 lang 时清空
}
```

- `triggerFirstScoring`：置 `isScoringAcceptance=true` → `apiClient.postAcceptanceScore(jobId, {lang, audience_baseline})` → `setAcceptanceScore` 覆盖（含 `isScoringAcceptance=false`）；失败 → `isScoringAcceptance=false`，`acceptanceScore` 保持 -1，console.error。
- `triggerDeltaScoring`：置 `isScoringAcceptance=true` → `apiClient.postAcceptanceScoreDelta(jobId, {lang, risk_index})` → `setAcceptanceScore` 覆盖；失败 → 保留旧分，toast「评分刷新失败，已显示旧分」。
- `setAcceptanceScore`：partial merge 到 `LangResult`。
- `clearAcceptanceScore`：reset 该 lang 的评分字段；在 `resetAll` 和 `setResult({status:"idle"})` 时调用。

`jobId` 从 `workspace-store` 取（`currentJobId`），与 `loadDecisionLogs` 拿 `resultId` 同模式。

### `api-client.ts` 新增方法

```ts
async postAcceptanceScore(jobId: string, body: { lang: string; audience_baseline: AudienceBaseline }): Promise<AcceptanceScorePayload> {
  return this.post(`/api/jobs/${jobId}/acceptance-score`, body);
}
async postAcceptanceScoreDelta(jobId: string, body: { lang: string; risk_index: number }): Promise<AcceptanceScorePayload> {
  return this.post(`/api/jobs/${jobId}/acceptance-score/delta`, body);
}

interface AcceptanceScorePayload {
  total_score: number;            // -1 失败
  dimensions: DimensionScores;
  confidence: number;
  top3_risk_indices: number[];
  audience_baseline: AudienceBaseline;
}
```

### 后端端点签名调整（方案 A）

`backend/app/api/jobs.py`：

- `AcceptanceScoreDeltaRequest` 改为 `{lang: str, risk_index: int}`（去掉 `sentence_id`/`new_text`）。
- `_run_acceptance_delta(result, risk_index, ...)`：
  1. 读 `risk_annotations[risk_index]`，取其 `offset`（accept/revert 路由已重算）；越界 400。
  2. `segment(result.translated_text, lang)` 重切，找 `char_offset <= offset < char_offset+length` 的句 → `target_sentence_id`（对应缓存里的 `s{i}`）；找不到（offset=-1 或边界漂移）→ 400「cannot locate sentence」。
  3. 复用现有 `score_sentence_single` + `affects_neighbors` 邻接句逻辑重算 → 聚合写回 → 返回。
- delta 的 decision_log `metadata` 仍记 `trigger="sentence_replace"`、`affected_sentence_ids`（含邻接句），新增 `risk_index`。
- 测试更新：`test_delta_rescoring_updates_score`、`test_delta_neighbor_rescore_when_affects_neighbors`、集成测试改发 `risk_index`；删 `sentence_id`/`new_text` 入参。

### `DecisionLogEntry` 类型补 `acceptance` stage

前端 `lib/api-client.ts` 的 `DecisionLogEntry.stage` 联合类型目前缺 `"acceptance"`（后端 Task 7 加的）。补上，否则 decision-log 面板的 `STAGE_ORDER` 过滤会漏掉 acceptance 条目。

## 6. 错误处理与降级

前端是 UI 层，降级原则：**评分失败不能阻塞译文展示和风险操作**。评分是附加反馈，不是必需。

### 首次评分失败

- API 4xx/5xx/网络错 → `isScoringAcceptance=false`，`acceptanceScore` 保持 -1
- 面板显示空态：「接受度评分暂不可用」+ 一个「重试」按钮（调 `triggerFirstScoring`）
- 不 toast（首次失败不抢注意力；面板自身已表达）
- 不影响译文/风险标注展示

### Delta 重算失败

- API 失败 → 保留旧分（`setAcceptanceScore` 不调，`isScoringAcceptance=false`）
- toast「评分刷新失败，已显示旧分」（delta 是用户操作后的即时反馈，失败要告知）
- 不阻塞后续风险操作

### 受众基准切换失败

- 切换中途失败 → 保留旧分，受众基准按钮回退到切换前高亮（`audienceBaseline` 不更新）
- toast「受众基准切换失败」
- 面板不闪空（旧分一直在）

### 置信度标注（对齐后端 §6 阈值）

- `confidence >= 0.7` → 正常显示，总分 teal
- `0.3 <= confidence < 0.7` → 总分标灰 + 小字「评分置信度较低」
- `confidence < 0.3` → 总分标灰 + 小字「评分置信度低，仅供参考」
- 面板常驻小字：「基于 LLM 的接受度估计（受众基准：{audienceBaseline}），非审计级，仅供参考」

### accept-all 后的 delta 触发策略

- `accept-all` 批量接受所有 open 风险 → 多句都改了译文，单句 delta 不够
- **策略**：accept-all 完成后触发**一次首次评分**（全文重算），而非并发 delta（避免互相覆盖缓存）
- 代价：accept-all 后等 ~2s（全文重算），但 accept-all 本就是批量操作，用户预期等待
- 实现：`risk-detail-list.tsx` 的 accept-all handler 成功后追加 `triggerFirstScoring(lang, currentBaseline)`

### Loading 状态分层

- 首次评分 / 受众切换（全文）：`AcceptanceScoreSkeleton` 全面板骨架
- Delta（局部）：面板内容保留，仅总分区域一个小的 inline spinner（>500ms 才显示）；<500ms 无感知
- `isScoringAcceptance` 期间受众基准按钮 disabled（防切换中途再切换）

### 未支持场景

- 译文为空 / status 未 completed → 面板不渲染（条件渲染，不留空壳）
- `acceptanceScore === -1 && !isScoringAcceptance && status === completed` → 空态 + 重试按钮（首次失败）

## 7. 测试策略

贴合现有 vitest + @testing-library/react 模式，store 用 `vi.mock("@/stores/translation-store", ...)` selector 模式。

### 测试矩阵

1. **`AcceptanceDimensionBar`（纯展示）**：渲染标签+数值+条形；边界 0 分（0 宽）/ 25 分（满宽）；不依赖 store。
2. **`AcceptanceScoreSkeleton`（纯展示）**：渲染 3 行 pulse div；不依赖 store。
3. **`AcceptanceScorePanel`（mock store）**：
   - 首次评分触发：`status=completed` + `acceptanceScore=-1` → `triggerFirstScoring` 调一次（幂等：再渲染不重复）
   - 评分中：`isScoringAcceptance=true` → 渲染 Skeleton
   - 评分完成：`acceptanceScore=80` + dimensions + confidence=0.9 → 渲染总分、四维条、Top3
   - 低置信度：`confidence=0.2` → 总分标灰 + 「评分置信度低」小字
   - 空态（首次失败）：`completed` + `-1` + `!isScoring` → 「暂不可用」+ 重试按钮 → 点击调 `triggerFirstScoring`
   - 受众基准切换：点 `academic` → `triggerFirstScoring(lang, "academic")`；`isScoringAcceptance` 时按钮 disabled
   - Top3 点击联动：点 Top3 → `window.dispatchEvent` with `scroll-to-risk-mark` + `detail.index`；`setResult(lang, {highlightedIndex: index})` 被调
   - 未渲染条件：`status != completed` 或无 translatedText → 面板不渲染
   - 常驻小字：渲染「基于 LLM 的接受度估计（受众基准：policy_media），非审计级，仅供参考」
4. **Delta 集成（mock apiClient）**：`triggerDeltaScoring(lang, 2)` → `postAcceptanceScoreDelta` with `{lang, risk_index: 2}`；失败 → `setAcceptanceScore` 不调，`isScoringAcceptance` 回 false。
5. **Store action 单测（mock apiClient）**：`triggerFirstScoring` 成功 → `setAcceptanceScore` 用 payload 调，`isScoringAcceptance` 先 true 后 false；失败 → `acceptanceScore` 保持 -1，不抛。`triggerDeltaScoring` 同。`clearAcceptanceScore` → 字段回 undefined/-1。
6. **后端 delta 改签名后的回归（pytest）**：`test_delta_rescoring_updates_score` 发 `{lang, risk_index:1}` → 60；`test_delta_neighbor_rescore_when_affects_neighbors` 发 `{lang, risk_index:1}`；`test_delta_unknown_risk_index_returns_400`（新）；`test_delta_cannot_locate_sentence_returns_400`（新）；集成测试 delta 阶段发 `risk_index`。

### 不测的（诚实边界）

- 不测真实 LLM 评分与受众反应的相关性（同后端 spec，不可证）
- 不测 `<mark>` 滚动动画的视觉细节（jsdom 无 layout）
- 不测 p95 < 1s / < 2s 的真实延迟（需真实 LLM，靠后端 spec 保证；前端只测 >500ms spinner 显示逻辑）

### 测试文件布局

```
frontend/components/workspace/__tests__/
  acceptance-score-panel.test.tsx
  acceptance-dimension-bar.test.tsx
frontend/stores/__tests__/
  acceptance-store.test.ts
backend/tests/
  test_acceptance_api.py          # 更新 delta 测试 + 新增 2 个 400 测试
  test_acceptance_integration.py  # 更新 delta 阶段入参
```

覆盖率目标：纯展示组件行覆盖 > 95%；面板 + store 分支覆盖 > 80%。

## 8. 范围边界（YAGNI）

本前端 v1 不做：
- 评分历史趋势图（P3）
- 自定义受众基准（仅三预设）
- 评分导出（决策日志 PDF 导出是独立 P2 项，不耦合）
- 评分维度对比图（跨多次翻译）——P3
- delta 的逐句进度可视化（仅总分滚动更新 + 局部 spinner）
