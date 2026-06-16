# 风险标注原因解释建议改为简体中文 — 设计文档

**日期：** 2026-06-16
**状态：** 已审批

## 背景

当前风险标注系统中，LLM 提示词（`RISK_ANNOTATION_PROMPT` 和 `SUGGESTION_PROMPT`）全部为英文，导致：
- `explanation`（风险解释原因）输出为英文
- `reason`（建议替换理由）输出为英文
- `risk_type`（如 `cognitive_bias`）以英文 snake_case 原始值显示在前端

前端 UI 框架文字（风险级别标签、按钮）已是中文，但标注内容本身是英文，用户体验不一致。

## 方案选择

选择 **方案 A：提示词全中文 + 前端 risk_type 映射表**

- 提示词翻译成中文，让模型直接输出中文 explanation/reason
- `risk_type`/`risk_level` 枚举值保持英文（不破坏 API 数据格式）
- 前端加映射表显示中文标签
- 改动最小（2 个后端文件 + 2 个前端文件）

## 设计细节

### Section 1：后端提示词改动

**文件：** `backend/app/llm/prompts.py`

**RISK_ANNOTATION_PROMPT 改为中文：**
- 角色设定改为中文："你是一位文化风险分析师"
- 任务描述翻译成中文
- `risk_level` 和 `risk_type` 的枚举值保持英文（`low/medium/high`、`cognitive_bias/negative_association/ambiguity`），因为这些是结构化字段，前端依赖这些值做样式匹配
- `explanation` 输出指令改为："一句话解释风险原因，请用简体中文撰写"
- JSON 格式指令改为中文

**SUGGESTION_PROMPT 改为中文：**
- 角色设定改为中文："你是一位文化适配专家"
- `text` 保持目标语言输出不变（这是替换短语，必须是目标语言）
- `reason` 输出指令改为："简要解释为什么这个替换更好，请用简体中文撰写"
- JSON 格式指令改为中文

**不改动的：**
- `TRANSLATION_SYSTEM_PROMPT` 和 `STRATEGY_DESCRIPTIONS` 保持原样

### Section 2：前端 risk_type 映射表

**文件：** `frontend/components/workspace/risk-detail-list.tsx` 和 `risk-annotation-popover.tsx`

在两个组件中添加 `RISK_TYPE_LABELS` 常量：

```tsx
const RISK_TYPE_LABELS: Record<string, string> = {
  cognitive_bias: "认知偏差",
  negative_association: "负面联想",
  ambiguity: "歧义",
};
```

**显示逻辑：**
- `{annotation.risk_type}` → `{RISK_TYPE_LABELS[annotation.risk_type] ?? annotation.risk_type}`
- 未映射的值 fallback 为原始字符串显示

**不改动的：**
- `risk_level` 已有中文映射（高风险/中风险/低风险），保持不变
- `explanation` 和 `reason` 不需要前端映射，因为 LLM 会直接输出中文

## 影响范围

| 文件 | 改动类型 |
|------|----------|
| `backend/app/llm/prompts.py` | 翻译提示词为中文 |
| `frontend/components/workspace/risk-detail-list.tsx` | 加 RISK_TYPE_LABELS 映射 |
| `frontend/components/workspace/risk-annotation-popover.tsx` | 加 RISK_TYPE_LABELS 映射 |

## 数据兼容性

- 旧数据中 `explanation` 和 `reason` 是英文，新数据是中文 — 前端直接显示文本内容，无需兼容处理
- `risk_type` 和 `risk_level` 枚举值不变，API 格式完全兼容
- 无需数据迁移
