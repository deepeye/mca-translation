# 策略选项 Tooltip 设计

## 概述

为翻译策略选择器（信息等值 / 受众优先 / 直译参考）添加 hover tooltip，显示简要解释和适用场景。

## 改动范围

| 文件 | 操作 |
|------|------|
| `frontend/components/ui/tooltip.tsx` | 新增（shadcn 生成） |
| `frontend/components/workspace/strategy-selector.tsx` | 修改 |

## 实现

1. `npx shadcn@latest add tooltip` 生成 Tooltip 组件
2. 修改 `strategy-selector.tsx`：
   - STRATEGIES 数组增加 `desc` 和 `scenario` 字段
   - 每个 radio label 包一层 Tooltip
   - 组件顶层加 `<TooltipProvider>`

## Tooltip 内容

| 策略 | desc | scenario |
|------|------|----------|
| 信息等值 | 忠实保留原文语义，准确性优先于可读性 | 法律文书、外交文件、学术论文 |
| 受众优先 | 侧重目标受众可读性，必要时重构句式 | 宣传材料、营销文案、公共沟通 |
| 直译参考 | 最小化文化适配，逐句对照原文 | 专业翻译辅助、原文逐句核查 |

## Tooltip 布局

- 宽度 `w-56`
- 第一行：描述文字
- 第二行：`适用：{scenario}`（`text-muted-foreground`，11px）

## 代码结构

```tsx
const STRATEGIES: { value: Strategy; label: string; desc: string; scenario: string }[] = [
  { value: "semantic_equivalence", label: "信息等值",
    desc: "忠实保留原文语义，准确性优先于可读性",
    scenario: "法律文书、外交文件、学术论文" },
  { value: "audience_first", label: "受众优先",
    desc: "侧重目标受众可读性，必要时重构句式",
    scenario: "宣传材料、营销文案、公共沟通" },
  { value: "literal_reference", label: "直译参考",
    desc: "最小化文化适配，逐句对照原文",
    scenario: "专业翻译辅助、原文逐句核查" },
];

<TooltipProvider>
  <div className="flex gap-3 text-xs text-muted-foreground">
    {STRATEGIES.map((s) => (
      <Tooltip key={s.value}>
        <TooltipTrigger asChild>
          <label className="flex cursor-pointer items-center gap-1.5">
            <span className={...} onClick={() => setStrategy(s.value)} />
            <span>{s.label}</span>
          </label>
        </TooltipTrigger>
        <TooltipContent>
          <p>{s.desc}</p>
          <p className="text-muted-foreground text-[11px] mt-1">适用：{s.scenario}</p>
        </TooltipContent>
      </Tooltip>
    ))}
  </div>
</TooltipProvider>
```
