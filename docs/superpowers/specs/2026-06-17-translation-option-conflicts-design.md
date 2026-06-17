# 翻译选项冲突消解设计

**日期**: 2026-06-17
**状态**: 已批准,待实现

## Context(背景与动机)

CulturalBridge 的翻译有四个正交选项:`genre`(文体)、`strategy`(策略)、`cultural_sphere`(文化圈)、`audience_type`(受众)。它们在后端 `translation.py` 里被拼装进同一个 system prompt:

- `genre` + `strategy` → 注入 `TRANSLATION_SYSTEM_PROMPT`
- `cultural_sphere` + `audience_type` → 经 `cultural_preprocess` 预处理,作为 `<cultural_constraints>` 块追加

**问题**:某些组合在同一个 prompt 里产生矛盾指令。最严重的是**硬冲突**——当 `strategy=literal_reference`(直译参考,"最小化适配")且文化圈被设置、预处理发现高文化差异词时,`<cultural_constraints>` 里会强制注入 `[术语约束 - 必须遵守] MUST_USE explanatory 翻译`。于是 prompt 同时说"必须适配"和"最小化适配",LLM 只能随机选一个,结果不可预测。

次级张力:`literal_reference` + `genre=brand`(品牌传播)方向相反;`audience_first` + `policy` 有张力等。

**目标**:用前端禁止的方式消除硬冲突,确保不会产生矛盾组合。范围**仅限硬冲突**,弱张力不限制以保持灵活性。

**决策摘要**(经 brainstorming 确认):
1. 处理策略:**前端限制 + 禁止**(最严格,从源头阻止矛盾组合)
2. 范围:**只编码硬冲突**
3. 实现路径:**方案 A**——纯函数模块 + 选择器驱动禁用(逻辑集中可测、store 无副作用、后端零改动)

## 已验证前提

后端完全支持 `cultural_sphere`/`audience_type` 为 `None`,**零改动**:

- `backend/app/schemas/job.py:27-28`:`cultural_sphere: Optional[str] = None`、`audience_type: Optional[str] = None`
- `backend/app/tasks.py:56`:`if job.cultural_sphere:` 守卫,为 None 时跳过 preprocess
- `backend/app/services/translation.py:35`:为 None 时不注入 `<cultural_constraints>` 块,prompt 自洽

因此前端只需在直译模式下把两字段传 `null`,硬冲突从根上消除。

## 冲突规则(真相源)

新增 `frontend/lib/translation-conflicts.ts`,纯函数,无副作用。所有选择器从这里读,这是**唯一的规则定义点**。

```ts
import type { Genre, Strategy } from "@/stores/workspace-store";

export const LITERAL_MODE_STRATEGY: Strategy = "literal_reference";

/** 是否处于纯直译模式(该策略下不做文化适配) */
export function isLiteralMode(strategy: Strategy): boolean {
  return strategy === LITERAL_MODE_STRATEGY;
}

/** 给定策略,返回被禁用的文体(规则 1:literal_reference ↔ brand) */
export function getDisabledGenres(strategy: Strategy): Genre[] {
  return isLiteralMode(strategy) ? ["brand"] : [];
}

/** 给定文体,返回被禁用的策略(规则 1 的反向) */
export function getDisabledStrategies(genre: Genre): Strategy[] {
  return genre === "brand" ? ["literal_reference"] : [];
}
```

**编码的两条规则**:
- 规则 1:`literal_reference` 与 `brand` 互斥(双向禁用)
- 规则 2:`literal_reference` = 纯直译模式,禁用文化圈 + 受众选择器(由 `isLiteralMode` 驱动,见下节)

弱张力(`audience_first`+`policy`、`diaspora_chinese`+非中文文化圈等)**不编码**,保持灵活。

## UI 响应

### 双向禁用(GenreSelector × StrategySelector)

两个选择器分别用对方的当前值算出自己该禁用哪些项:

- `GenreSelector` 读 `strategy`,调用 `getDisabledGenres(strategy)` 算出禁用的 genre。当 `strategy=literal_reference` 时,`brand` 按钮:`opacity-50 cursor-not-allowed`、不可点击、tooltip "与直译参考策略冲突"。
- `StrategySelector` 读 `genre`,调用 `getDisabledStrategies(genre)` 算出禁用的 strategy。当 `genre=brand` 时,`literal_reference` radio 同样置灰 + tooltip "与品牌传播文体冲突"。

**数据流**:只读禁用,**不改 store**。store 里的 `genre`/`strategy` 值不变,只是 UI 不让选这个组合。

### 纯直译模式(`isLiteralMode` 时)

当选中 `literal_reference` 时:

- `CultureSphereSelector`、`AudienceTypeSelector` 整体置灰(`opacity-50`、`pointer-events-none`),并在上方加一行提示:`直译参考模式下不进行文化适配`。
- 选择器视觉禁用但仍**显示当前值**(保留用户的选择,避免来回切换丢失)。

## 数据流 / 后端契约

`InputPanel.handleTranslate` 发请求时,在直译模式下把两个字段传 `null`:

```ts
import { isLiteralMode } from "@/lib/translation-conflicts";

// 在 apiClient.post("/api/jobs", {...}) 内:
cultural_sphere: isLiteralMode(store.input.strategy) ? null : store.input.culturalSphere,
audience_type: isLiteralMode(store.input.strategy) ? null : store.input.audienceType,
```

后端收到 `null` → 跳过 preprocess → 不注入 `<cultural_constraints>` 块 → prompt 自洽。store 里保留用户选的文化圈/受众值(切出直译模式即恢复生效)。

## 边界情况

- **genre=brand 且用户点 literal_reference**:点不动(禁用),tooltip 解释。需先改 genre。
- **strategy=literal_reference 且用户切 genre 到 brand**:brand 按钮禁用,点不动。
- **切换出直译模式**:文化圈/受众选择器恢复可点,原值仍在(因 store 从未清除)。
- **直译模式下的 CulturalAdaptationPanel**:后端不返回 `cultural_adaptation`(为 null),`CulturalAdaptationPanel` 已有 `if (!adaptation) return null` 早退,自然不显示,无需改动。

## 改动文件

| 文件 | 改动 |
|---|---|
| `frontend/lib/translation-conflicts.ts` | **新增**:冲突规则纯函数 |
| `frontend/lib/translation-conflicts.test.ts` | **新增**:纯函数单测 |
| `frontend/components/workspace/genre-selector.tsx` | 读 `strategy` 禁用 `brand`(规则 1) |
| `frontend/components/workspace/strategy-selector.tsx` | 读 `genre` 禁用 `literal_reference`(规则 1) |
| `frontend/components/workspace/culture-sphere-selector.tsx` | `isLiteralMode` 时整体置灰 + 提示 |
| `frontend/components/workspace/audience-type-selector.tsx` | `isLiteralMode` 时整体置灰 + 提示 |
| `frontend/components/workspace/input-panel.tsx` | payload 在直译模式传 `null` |

**后端零改动。**

## 测试策略

- `translation-conflicts.test.ts`(纯函数单测):
  - `isLiteralMode("literal_reference") === true`,其他策略为 `false`
  - `getDisabledGenres("literal_reference")` 等于 `["brand"]`,其他策略为 `[]`
  - `getDisabledStrategies("brand")` 等于 `["literal_reference"]`,其他文体为 `[]`
- 手动验证端到端:
  - 选 `literal_reference` → 文化圈/受众选择器置灰 + 提示出现
  - `genre=brand` 时 `literal_reference` radio 置灰、点不动
  - 触发一次直译翻译,检查请求 payload 中 `cultural_sphere`/`audience_type` 为 `null`,响应不含 `cultural_adaptation`
  - 切换出直译模式,文化圈/受众恢复可点且保留原值

## 非目标(YAGNI)

- 不编码弱张力(`audience_first`+`policy` 等),保持灵活性
- 不做后端 prompt 调和(降级 MUST_USE 为 SUGGEST 之类)——前端禁止已从源头消除矛盾
- 不给 `cultural_sphere` 加"不指定"选项——直译模式由 `strategy` 驱动,无需新增文化圈空选项
- 不在 store setter 里加副作用(避免静默拒绝的坏 UX)
