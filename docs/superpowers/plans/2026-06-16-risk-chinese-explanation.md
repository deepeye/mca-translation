# 风险标注中文解释 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将风险标注的 explanation/reason 改为简体中文输出，risk_type 在前端显示中文标签

**Architecture:** 修改 LLM 提示词为全中文，让模型直接输出中文 explanation/reason；risk_type 枚举值保持英文不变，前端加映射表显示中文标签

**Tech Stack:** Python (FastAPI/Celery), TypeScript (Next.js/React), LLM prompt engineering

---

### Task 1: 修改 RISK_ANNOTATION_PROMPT 为中文

**Files:**
- Modify: `backend/app/llm/prompts.py:18-34`

- [ ] **Step 1: 替换 RISK_ANNOTATION_PROMPT 为中文版本**

将 `prompts.py` 中 `RISK_ANNOTATION_PROMPT` 的英文内容替换为中文。枚举值 `risk_level` 和 `risk_type` 保持英文不变。

```python
RISK_ANNOTATION_PROMPT = """你是一位文化风险分析师。请根据下面的原文中文和其译文，识别译文中可能在目标受众中引起误解、负面联想或认知偏差的表达。

对每个风险，请提供：
- 译文中对应的原文短语（span text）
- risk_level："low"、"medium" 或 "high"
- risk_type："cognitive_bias"、"negative_association" 或 "ambiguity"
- explanation：一句话解释风险原因，请用简体中文撰写

返回 JSON 数组。如果没有发现风险，返回空数组。

原文中文：
{source_text}

译文（{target_language}）：
{translated_text}

只返回 JSON 数组，不要包含其他文本。"""
```

- [ ] **Step 2: 运行后端服务器验证无语法错误**

Run: `cd backend && python -c "from app.llm.prompts import RISK_ANNOTATION_PROMPT; print(RISK_ANNOTATION_PROMPT[:50])"`
Expected: 输出中文提示词开头，无 ImportError

- [ ] **Step 3: Commit**

```bash
git add backend/app/llm/prompts.py
git commit -m "feat: translate RISK_ANNOTATION_PROMPT to Simplified Chinese"
```

---

### Task 2: 修改 SUGGESTION_PROMPT 为中文

**Files:**
- Modify: `backend/app/llm/prompts.py:36-52`

- [ ] **Step 1: 替换 SUGGESTION_PROMPT 为中文版本**

将 `prompts.py` 中 `SUGGESTION_PROMPT` 的英文内容替换为中文。`text` 输出保持目标语言不变，`reason` 改为中文。

```python
SUGGESTION_PROMPT = """你是一位文化适配专家。请根据原文中文、其译文以及译文中已识别的风险表达，建议 1-2 个适合目标受众的文化替换短语，以降低风险。

对每个建议，请提供：
- text：替换短语（使用目标语言）
- reason：简要解释为什么这个替换更好，请用简体中文撰写

原文中文：
{source_text}

译文（{target_language}）：
{translated_text}

风险表达："{phrase}"
风险类型：{risk_type}
风险解释：{explanation}

返回 JSON 数格式的建议数组。只返回 JSON 数组，不要包含其他文本。"""
```

- [ ] **Step 2: 运行后端验证无语法错误**

Run: `cd backend && python -c "from app.llm.prompts import SUGGESTION_PROMPT; print(SUGGESTION_PROMPT[:50])"`
Expected: 输出中文提示词开头，无 ImportError

- [ ] **Step 3: Commit**

```bash
git add backend/app/llm/prompts.py
git commit -m "feat: translate SUGGESTION_PROMPT to Simplified Chinese"
```

---

### Task 3: 前端 risk-detail-list.tsx 加 risk_type 中文映射

**Files:**
- Modify: `frontend/components/workspace/risk-detail-list.tsx:9-13` (在 RISK_BADGE_STYLES 后加映射表)
- Modify: `frontend/components/workspace/risk-detail-list.tsx:164-165` (替换 risk_type 显示)

- [ ] **Step 1: 在 RISK_BADGE_STYLES 常量后面添加 RISK_TYPE_LABELS**

在 `risk-detail-list.tsx` 第 13 行（`RISK_BADGE_STYLES` 定义结束）之后插入：

```tsx
const RISK_TYPE_LABELS: Record<string, string> = {
  cognitive_bias: "认知偏差",
  negative_association: "负面联想",
  ambiguity: "歧义",
};
```

- [ ] **Step 2: 替换 risk_type 显示为中文标签**

将第 164-165 行的 `{annotation.risk_type}` 替换为 `{RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}`：

原代码：
```tsx
<span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[9px] text-[#475569]">
  {annotation.risk_type}
</span>
```

替换为：
```tsx
<span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[9px] text-[#475569]">
  {RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}
</span>
```

- [ ] **Step 3: 运行 TypeScript 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/components/workspace/risk-detail-list.tsx
git commit -m "feat: add RISK_TYPE_LABELS Chinese mapping in risk-detail-list"
```

---

### Task 4: 前端 risk-annotation-popover.tsx 加 risk_type 中文映射

**Files:**
- Modify: `frontend/components/workspace/risk-annotation-popover.tsx:6-10` (在 RISK_STYLES 后加映射表)
- Modify: `frontend/components/workspace/risk-annotation-popover.tsx:31-32` (替换 risk_type 显示)

- [ ] **Step 1: 在 RISK_STYLES 常量后面添加 RISK_TYPE_LABELS**

在 `risk-annotation-popover.tsx` 第 10 行（`RISK_STYLES` 定义结束）之后插入：

```tsx
const RISK_TYPE_LABELS: Record<string, string> = {
  cognitive_bias: "认知偏差",
  negative_association: "负面联想",
  ambiguity: "歧义",
};
```

- [ ] **Step 2: 替换 risk_type 显示为中文标签**

将第 31-32 行的 `{annotation.risk_type}` 替换为 `{RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}`：

原代码：
```tsx
<span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] text-[#475569]">
  {annotation.risk_type}
</span>
```

替换为：
```tsx
<span className="inline-flex items-center rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] text-[#475569]">
  {RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}
</span>
```

- [ ] **Step 3: 运行 TypeScript 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/components/workspace/risk-annotation-popover.tsx
git commit -m "feat: add RISK_TYPE_LABELS Chinese mapping in risk-annotation-popover"
```

---

### Task 5: 集成验证 — 启动前后端测试完整流程

**Files:** 无新文件改动，验证已有改动

- [ ] **Step 1: 启动后端服务器**

Run: `cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --reload --port 8000`
Expected: 服务器正常启动

- [ ] **Step 2: 启动 Celery worker**

Run: `cd backend && source .venv/bin/activate && celery -A app.celery_app worker --loglevel=info --concurrency=2`
Expected: Worker 正常连接

- [ ] **Step 3: 启动前端**

Run: `cd frontend && npm run dev`
Expected: 前端编译成功

- [ ] **Step 4: 在浏览器中触发一次翻译任务，检查风险标注输出**

在浏览器中访问 http://localhost:3000/workspace，输入一段中文文本，选择目标语言，点击"开始转译"。

等待翻译完成后，检查：
1. 风险标注的 `explanation` 是否为简体中文
2. 风险类型标签显示是否为中文（"认知偏差"/"负面联想"/"歧义"）
3. 点击"查看替代方案"后，`reason` 是否为简体中文

- [ ] **Step 5: 如果一切正常，做最终 commit（如有遗漏修复）**

如果有遗漏修复：
```bash
git add -A && git commit -m "fix: minor adjustments for Chinese risk annotations"
```

如果没有遗漏，跳过此步。
