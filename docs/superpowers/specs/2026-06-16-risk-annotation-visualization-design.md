# 风险标注可视化设计文档

**日期**: 2026-06-16
**状态**: 已确认
**范围**: P0 增补——将后端已有的 risk_annotations 数据在前端可视化

---

## 1. 背景

后端 `risk_annotations` 已正确返回（含 `phrase`, `risk_level`, `risk_type`, `explanation`），但前端仅 `RiskSummary` 组件显示汇总条（"2 处风险 🔴1 高风险 🟡1 中风险"），没有：
- 译文中标注风险短语的具体位置
- 点击/悬停查看详情的交互

---

## 2. 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 标记样式 | 左侧竖线 + 淡底 | 兼顾存在感与可读性，与现有 risk-summary 的 border-left 一致 |
| 详情展示 | Popover + 卡片列表 | 风险解释通常 50-100 字，卡片比表格更自然 |
| 短语定位 | `String.indexOf()` 匹配 phrase | P0 简单可靠；后续可升级为 span offset |
| 联动高亮 | 列表 hover ↔ 译文标记双向 | 用户既从译文找列表，也从列表找译文 |

---

## 3. 组件架构

### 新增/修改组件

**`TranslationResult`（修改）**
- 当前：纯文本 `<div>` 渲染 `translatedText`
- 改为：解析 `riskAnnotations`，将风险短语渲染为 `<mark>` 标签
- 每个 `<mark>` 样式：`border-left: 3px solid <风险色>` + `background: <淡色>`
- `onMouseEnter` → 显示 `RiskAnnotationPopover`
- `onClick` → 通知下方列表滚动到对应卡片

**`RiskAnnotationPopover`（新增）**
- 使用 shadcn/ui `Popover` 组件
- 内容：风险等级 badge + `risk_type` 标签 + 解释文本（截断 2 行）
- 触发方式：hover 译文中的 `<mark>` 标签

**`RiskDetailList`（新增，替代 `RiskSummary`）**
- 保留汇总条（N 处风险 + 等级计数）
- 下方卡片列表，每条：等级 badge + 短语 + 完整解释
- hover 列表卡片 → 译文中对应标记背景加深 + 字重加粗
- click 列表卡片 → 译文滚动到对应标记位置

**`RiskSummary`（移除）** — 被 `RiskDetailList` 替代

### 组件树（更新后）

```
<OutputPanel>
  <LanguageTabs>
  <TranslationResult>
    <mark> (× N 风险短语)
    <RiskAnnotationPopover>  ← hover 触发
  <RiskDetailList>           ← 替代 RiskSummary
    <汇总条>
    <RiskDetailCard> (× N)
  <ResultActions>
```

---

## 4. 数据流

### 风险短语定位

```typescript
// 在 translatedText 中查找每个 phrase 的首次出现位置
function locateRisks(text: string, annotations: RiskAnnotation[]): RiskSpan[] {
  const usedOffsets = new Set<number>();
  return annotations
    .map((a, index) => {
      const offset = text.indexOf(a.phrase);
      if (offset === -1) return null;
      // 避免重叠：跳过已被占用的 offset
      if (usedOffsets.has(offset)) return null;
      usedOffsets.add(offset);
      return { index, phrase: a.phrase, offset, length: a.phrase.length, ...a };
    })
    .filter(Boolean)
    .sort((a, b) => a.offset - b.offset);
}
```

渲染时按 offset 顺序将 `translatedText` 分段，风险短语用 `<mark>` 包裹。

### 状态管理

`translation-store` 的 `LangResult` 新增：

```typescript
highlightedIndex: number | null;  // 当前高亮的风险项索引，null = 无高亮
```

联动逻辑：
- 译文 `<mark>` hover → `setResult(lang, { highlightedIndex: i })`
- 列表卡片 hover → `setResult(lang, { highlightedIndex: i })`
- 两者 mouseLeave → `setResult(lang, { highlightedIndex: null })`

---

## 5. 视觉规格

### 译文内标记

| 风险等级 | border-left | background | badge bg | badge text |
|----------|-------------|------------|----------|------------|
| 高 | `#EF4444` (3px solid) | `rgba(239,68,68,0.08)` | `#FEE2E2` | `#DC2626` |
| 中 | `#EA580C` (3px solid) | `rgba(234,88,12,0.06)` | `#FFEDD5` | `#C2410C` |
| 低 | `#EAB308` (3px solid) | `rgba(234,179,8,0.06)` | `#FEF9C3` | `#A16207` |

高亮态（hover/联动）：background 透明度 ×2，font-weight → 600

### Popover

- 白色背景，1px border #E2E8F0，8px 圆角，阴影 `0 4px 20px rgba(0,0,0,0.12)`
- 顶部：等级 badge + risk_type 标签（灰底 #F1F5F9）
- 正文：解释文本，截断 2 行，line-height 1.6
- 触发：hover <mark>，延迟 150ms 显示/隐藏（防闪烁）

### 卡片列表

- 汇总条：border-left 3px #C2410C，背景 #FFF7ED，与当前 RiskSummary 一致
- 卡片：白色背景，1px border #E2E8F0，6px 圆角
- 卡片高亮态：border 变为对应风险色（#FCA5A5 / #FDBA74）
- 布局：等级 badge + 短语（font-weight 500-600）+ risk_type 标签 + 完整解释

---

## 6. 交互规格

| 操作 | 效果 |
|------|------|
| Hover 译文 `<mark>` | 弹出 Popover（等级 + 类型 + 截断解释）；标记背景加深 |
| Click 译文 `<mark>` | Popover 保持 + 下方列表滚动到对应卡片并高亮边框 |
| Hover 列表卡片 | 卡片边框变为风险色；译文中对应标记背景加深 + 字重加粗 |
| Click 列表卡片 | 译文滚动到对应标记位置 |
| MouseLeave | Popover 消失；高亮清除 |

---

## 7. 实现范围

**修改的文件：**
- `frontend/components/workspace/translation-result.tsx` — 重写为带内联标记的渲染
- `frontend/components/workspace/output-panel.tsx` — RiskSummary → RiskDetailList
- `frontend/stores/translation-store.ts` — LangResult 新增 highlightedIndex

**新增的文件：**
- `frontend/components/workspace/risk-annotation-popover.tsx` — Popover 组件
- `frontend/components/workspace/risk-detail-list.tsx` — 替代 RiskSummary

**删除的文件：**
- `frontend/components/workspace/risk-summary.tsx` — 被 RiskDetailList 替代

**不涉及：** 后端、API、数据模型——均无变更

---

*CulturalBridge 风险标注可视化设计 | 2026-06-16*
