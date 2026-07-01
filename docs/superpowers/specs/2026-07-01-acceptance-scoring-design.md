# 接受度评分（Acceptance Scoring）设计文档

> P2 功能。对转译后的译文输出 0–100 的受众接受度分数 + 维度分解，作为转译完成后的即时反馈，与风险标注联动。
>
> 定位：PRD §4.2「受众认知风险预测」。交付标准（PRD 第九章 P2）：稳定且有辨识度。

## 1. 背景与核心取舍

PRD §4.2 原方案要求「目标语言主流媒体语料训练的 BERT 分类器，按语言分别训练，导出 ONNX」，理由是 LLM 在评估任务上有政治立场漂移、与真实受众反应相关性难验证。

但本项目全栈为百炼 DashScope LLM，无自训练模型基础设施，单开发者模式。自训英/德/日 BERT 分类器是独立 ML 工程（语料采集 + 接受度标注 + 训练 + ONNX 链路 + 独立部署），且「接受度 ground truth」本身是开放研究问题，P2 周期内不可行。BERT 方案更适合放 P3 的「精致且有完整文档」目标。

本设计采用 **LLM-Judge + 校准层**：用 qwen-max 打分，但通过固定 rubric + JSON schema 强约束、多次采样取中位数、置信度标注、受众画像注入、UI 诚实标注「非审计级」等手段，把 PRD 担忧的漂移降级为「可观测」而非「不可证」。PRD §4.2 第三段交互流程原样保留，只换引擎。

PRD §4.2 第四段的三条应对策略（受众基准可切、标注仅供参考、建议非限制）在本设计全部承接。

## 2. 关键决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 与审校服务关系 | **完全独立维度** | 审校问「译得准不准」，接受度问「受众接不接受」，命题不同就该维度不同；PRD §4.2 是即时反馈定位，与审校独立深度审校天然分层 |
| 评分引擎 | **LLM-Judge + 校准层** | 复用 `bailian_client`，2–3 周可交付，与现有 services 全 LLM 架构同构；schema + 采样 + 置信度标注把漂移降为可观测；BERT 版本留作 P3 |
| 与 risk_annotation 关系 | **评分消费现有标注、不另造高亮** | 现有风险标注系统已完整落地，接受度评分定位是「给总分 + 维度分解」，风险词只是支撑总分的外在表现，没必要造第二套高亮 |
| Delta 重算 | **句级重算、单次采样** | 接受度本质是句级粒度的受众感受；单句 prompt 短可压到 <1s；跨句语义损失是诚实代价 |
| 语言范围 | **全五语言（英/德/日/西/法）** | PRD 限制三语言的唯一原因是 BERT 要按语言训练；换 LLM 后该约束根因消解，qwen-max 原生多语言 |

## 3. 架构与组件

新增独立服务模块，与现有 `risk_annotation` / `review` / `decision_log` 同层、松耦合。

```
backend/app/services/acceptance_scoring.py   # 评分服务（核心）
backend/app/llm/prompts.py                   # 新增 ACCEPTANCE_SCORE_PROMPT
backend/app/schemas/acceptance.py            # Pydantic schema（评分输出契约）
backend/app/api/jobs.py                      # 挂载评分调用点
```

### 组件职责

| 组件 | 职责 | 依赖 |
|---|---|---|
| `AcceptanceScorer` | 对一段译文 + 受众基准，调 LLM-Judge 返回 `{score, dimensions, risk_phrase_offsets, confidence, affects_neighbors, rationale}`。纯计算、无状态。 | `bailian_client`、`ACCEPTANCE_SCORE_PROMPT` |
| `SentenceSegmenter` | 按目标语言句末标点切句，返回 `[(sentence_id, text, char_span)]`。供评分和 delta 重算共用。 | 无（纯函数） |
| `AcceptanceAggregator` | 把句级评分聚合成全文总分（加权平均 + 风险词数惩罚）。替换后只重算受影响句，复用此聚合。 | `AcceptanceScorer` 输出 |
| `RiskPhraseMapper` | 把 LLM-Judge 识别的风险短语映射到现有 `risk_annotation` 的 mark 区间（按文本偏移对齐），不产第二套高亮。命中现有标注则引用其 id，未命中的只进 rationale 文字。 | `risk_annotation` 输出 |
| API 层 | `POST /jobs/{id}/acceptance-score`（首次评分）；`POST /jobs/{id}/acceptance-score/delta`（替换后句级重算）。 | `AcceptanceScorer`、`Aggregator` |

### 与既有系统的边界

- 复用 `bailian_client`，不新增 LLM 客户端
- 复用 `risk_annotation` 的 mark 高亮，`RiskPhraseMapper` 只做对齐映射
- 评分推理作为 `acceptance` 阶段写入 `decision_log`（现有阶段枚举 `preprocess/cultural_detect/glossary/translate/risk/suggestion` 新增 `acceptance`）
- 评分独立于 `review` 服务，不共享维度

### 设计原则

`SentenceSegmenter` 和 `RiskPhraseMapper` 是纯函数/纯映射，可单测不依赖 LLM；`AcceptanceScorer` 封装所有 LLM 调用与采样校准逻辑；`Aggregator` 隔离句级→全文的聚合策略（后续调权重只动这一个文件）。每个文件聚焦、可独立 hold 在上下文里。

### 待定调参常数（实现时定初值，spec 不硬编码）

- 句级聚合权重（默认等权，按句长加权可选）
- 风险词数惩罚系数（每条风险词扣几分）
- 采样方差阈值（超过则 `confidence=low`）
- 置信度标灰阈值（0.7 / 0.3，§6 已定）

这些是调参常数，初值在实现计划中给出，后续可基于实测调整，不属于设计决策。

## 4. 数据流

### 首次评分（转译完成后）

```
转译管线结束（译文 + risk_annotation 标注已生成）
        │
        ▼
API: POST /jobs/{id}/acceptance-score
  body: { audience_baseline: "policy_media" | "academic" | "social_media" }
        │
        ▼
SentenceSegmenter 切句 → [s0, s1, ..., sn]
        │
        ▼
AcceptanceScorer 对每句评分（批量并发，受 LLM 并发上限节流）
  每句: T=0.3 × 3 次采样 → 取中位数 → 方差>阈值标 confidence=low
  返回 {sentence_score, dimensions{audience,cultural,naturalness,risk},
        risk_phrase_offsets[], rationale, affects_neighbors}
        │
        ▼
RiskPhraseMapper: LLM 识别的风险短语 → 对齐到现有 risk_annotation mark 区间
  命中现有标注 → 引用其 id（不新增高亮）
  未命中 → 只进 rationale 文字（不新增高亮）
        │
        ▼
AcceptanceAggregator: 句级 → 全文
  全文总分 = Σ(sentence_score × 权重) - 风险词数惩罚
  全文维度分 = Σ(dimensions[d] × 权重)
  全文置信度 = min(句置信度)  // 任一句低置信则全文标低
        │
        ▼
写入 TranslationJob（acceptance_score / audience_baseline /
                     acceptance_confidence / dimensions JSON / sentence_scores JSON）
写入 decision_log（阶段=acceptance，记录各句评分理由）
        │
        ▼
返回前端: { total_score, dimensions, top3_risk_refs[], confidence }
  top3 取自 risk_annotation 按风险等级排序的前 3 条
```

### Delta 重算（用户替换某风险词后）

```
用户对某 mark 执行 accept（采纳替换建议）
        │
        ▼
前端: POST /jobs/{id}/acceptance-score/delta
  body: { sentence_id: "s3", new_text: "..." }
        │
        ▼
AcceptanceScorer 只重算 s3（单次采样，非 3 次 —— 换速度）
  邻接句 s2/s4 是否重算: 由 LLM 在 s3 评分时输出 "affects_neighbors: bool"
  若 true → 追加重算 s2/s4（仍各单次采样）
        │
        ▼
AcceptanceAggregator: 用新句分替换旧句分，重算全文总分（纯本地计算，<50ms）
        │
        ▼
返回前端: { total_score, dimensions, confidence }  // delta 结果
        │
        ▼
前端右侧面板分数滚动更新（spinner >500ms 才显示，PRD 第 791 行）
```

### 性能目标对照（PRD 第十章）

- 首次评分 p95 < 2s：句级并发 + 短 prompt（< 100 token 译文片段 + rubric）+ 3 次采样并发（非串行）
- Delta 重算 p95 < 1s：1–3 句 × 单次采样 + 本地聚合

## 5. 数据模型

对齐 PRD 第 596 行预留字段，在 `TranslationJob` 上新增列，不另建实体（评分是 Job 的派生属性，无独立查询/跨任务复用需求，符合 PRD 第 653 行「独立实体只在需独立查询或跨任务复用时才拆分」原则）。

### `TranslationJob` 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `acceptance_score` | `Integer, default=-1` | 全文总分 0–100；-1 未计算/失败（PRD 第 596 行已预留） |
| `audience_baseline` | `String(32), nullable` | `policy_media` / `academic` / `social_media`（PRD 第 597 行已预留） |
| `acceptance_confidence` | `Float, default=0.0` | 0–1，取句置信度最小值；< 阈值 UI 标灰 |
| `acceptance_dimensions` | `JSON, nullable` | `{audience, cultural, naturalness, risk}` 各 0–25，聚合后值 |
| `acceptance_sentence_scores` | `JSON, nullable` | `[{sentence_id, score, dimensions, confidence}]` 句级缓存，供 delta 重算复用（免重切句） |

迁移：`alembic revision --autogenerate -m "add acceptance scoring fields"` + `alembic upgrade head`。

### `DecisionLog` 条目

- 阶段枚举扩展：现有 `preprocess/cultural_detect/glossary/translate/risk/suggestion` + **`acceptance`**
- 首次评分：写一条 `acceptance` 阶段记录，metadata 含 `audience_baseline`、各句评分、方差/置信度、未命中标注的风险短语（进 rationale）
- Delta 重算：写一条 `acceptance` 阶段记录，metadata 标 `trigger=sentence_replace`、`affected_sentence_ids`、新旧句分对比

### Pydantic schema（`schemas/acceptance.py`）

```python
class DimensionScores(BaseModel):
    audience: float        # 受众匹配度 0-25
    cultural: float        # 文化敏感度 0-25
    naturalness: float     # 表达自然度 0-25
    risk: float            # 风险词密度分 0-25（越高越好=风险越少）

class SentenceScore(BaseModel):
    sentence_id: str
    score: int             # 0-100，-1 失败
    dimensions: DimensionScores
    confidence: float      # 0-1
    risk_phrase_offsets: list[tuple[int,int]]  # 句内字符偏移，供 Mapper 对齐
    affects_neighbors: bool  # delta 重算时 LLM 输出
    rationale: str         # 中文理由（含未命中标注的风险短语解释）

class AcceptanceResult(BaseModel):
    total_score: int
    dimensions: DimensionScores
    confidence: float
    top3_risk_refs: list[str]   # 引用 risk_annotation 的 mark id
    sentence_scores: list[SentenceScore]
```

## 6. 错误处理与降级

引擎是 LLM，失败模式比 BERT 分类器多。逐层降级，保证「评分可用」而非「评分完美」。

### LLM 调用失败（单句级）

- 超时/网络错/API 5xx → 重试 1 次（复用 `bailian_client` 既有重试）
- 仍失败 → 该句 `score=-1`、`confidence=0`、`rationale="该句评分失败：{错误类型}"`
- 聚合时：失败句按「该句维度取其余句均值」填补，`confidence` 取全文最低（失败句的 0 拉低全文置信度，UI 标灰）
- 不阻塞其余句评分（并发独立）

### LLM 输出 schema 不合规

- JSON 解析失败 / 缺字段 / 维度分超 0–25 → 重试 1 次（prompt 附加「上次输出格式错误，请严格按 schema」）
- 仍不合规 → 该句按失败处理
- 三次采样中部分合规：取合规采样的中位数；全不合规 → 失败

### 全文级降级

- 全部句失败 → `acceptance_score=-1`、面板显示「评分暂不可用，请稍后重试」+ 重试按钮
- 部分句失败（>50% 失败）→ 仍出分但 `confidence<0.3`，面板标灰 + 提示「评分置信度低，部分句子评估失败」

### Delta 重算降级

- 单句重算失败 → 保留旧句分，前端 toast「替换后评分刷新失败，已显示旧分」
- 不阻塞用户继续操作其他风险词

### 置信度阈值与 UI 标注

- `confidence >= 0.7` → 正常显示
- `0.3 <= confidence < 0.7` → 标灰 + 提示「评分置信度较低」
- `confidence < 0.3` → 标灰 + 提示「评分置信度低，仅供参考」
- **所有评分下方常驻小字**：「基于 LLM 的接受度估计（受众基准：{audience_baseline}），非审计级，仅供参考」

### 受众基准切换

- 切换 `audience_baseline` → 触发**全文重算**（非 delta，因为受众变了全文维度都变）
- 切换时面板 loading，期间保留旧分直至新分返回（不闪空）

### 并发与节流

- 首次评分：句级 LLM 调用并发，受百炼 QPS 上限节流（复用 `bailian_client` 信号量；若现有限流则新增）
- 3 次采样：同一句的 3 次采样并发（非串行），把单句延迟压到 ≈1 次采样时长
- 超长译文（>50 句）：分批，每批 10 句并发，避免一次性打满 QPS

## 7. 测试策略

逐组件可独立测试，LLM 调用全部 mock，不依赖真实百炼。

### 测试矩阵

1. **`SentenceSegmenter`（纯函数）**：英/德/日/西/法句末标点切分；边界（空文本、单句无标点、连续标点、超长句、含小数点/缩写 `Dr.` `Nr.` 误切）；char_span 准确性。
2. **`RiskPhraseMapper`（纯映射，mock risk_annotation）**：命中现有 mark → 引用 id；部分命中（跨 mark 边界）→ 取覆盖度最高 mark；未命中 → 不产高亮、进 rationale；现有标注为空 → 全部进 rationale。
3. **`AcceptanceAggregator`（纯计算）**：正常聚合；风险词数惩罚；失败句填补；全失败 → -1；delta 替换句分重算。
4. **`AcceptanceScorer`（mock `bailian_client`）**：3 次采样中位数；方差超阈值 → confidence=low；schema 不合规重试；全采样不合规 → 失败；`affects_neighbors` 透传；LLM 异常重试降级。
5. **API 层（FastAPI TestClient，mock Scorer）**：首次评分 200 + schema；未登录 401；他人 Job 403；delta 句级重算；受众切换全文重算。
6. **集成测试（1 个，全链路 mock LLM）**：转译完成 → 首次评分 → 写 Job 字段 + decision_log → 替换风险词 → delta 重算 → 总分变化 → decision_log 新增条目；验证 `acceptance` 阶段记录。

### 不测的（诚实边界）

- 不测 LLM 评分与「真实受众反应」的相关性——PRD §4.2 承认的不可证问题，LLM-Judge 版本更不可证，靠 confidence + UI 标注表达诚实
- 不做 A/B 对比 BERT（无 BERT 基线）

### 测试文件布局

```
backend/tests/test_sentence_segmenter.py
backend/tests/test_risk_phrase_mapper.py
backend/tests/test_acceptance_aggregator.py
backend/tests/test_acceptance_scorer.py
backend/tests/test_acceptance_api.py
backend/tests/test_acceptance_integration.py
```

覆盖率目标：纯函数组件（1/2/3）行覆盖 > 95%；Scorer/API/集成（4/5/6）分支覆盖 > 80%。

## 8. 性能指标对齐

| PRD 指标 | 目标 | 本设计达成方式 |
|---|---|---|
| 接受度评分计算延迟 | p95 < 2s | 句级并发 + 短 prompt + 3 次采样并发 |
| Delta 重算 | < 1s | 1–3 句单次采样 + 本地聚合 <50ms |
| 评分 spinner 阈值 | >500ms 显示 | 前端复用现有 spinner 约定 |

## 9. 范围边界（YAGNI）

本 P2 不做：
- BERT 分类器自训练（留 P3 审计级）
- 跨语言一致性审计（PRD §4.3，独立 P2 项）
- 接受度评分受众基准的「自定义」基准（仅三预设）
- 评分历史趋势分析（P3）
- 评分导出（决策日志 PDF 导出是独立 P2 项，本设计不耦合）
