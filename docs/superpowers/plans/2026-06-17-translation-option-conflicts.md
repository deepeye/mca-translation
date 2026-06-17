# 翻译选项冲突消解 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除翻译选项的硬冲突——在 UI 层禁止 `literal_reference`(直译参考)与 `brand`(品牌传播)组合,并把 `literal_reference` 定义为纯直译模式(禁用文化圈/受众选择器 + 后端请求传 null),使 system prompt 永不自相矛盾。

**Architecture:** 新增一个纯函数模块 `frontend/lib/translation-conflicts.ts` 作为冲突规则的唯一真相源;各选择器从中读取规则,把冲突选项视觉禁用(只读禁用,不改 store);`InputPanel` 在直译模式下把 `cultural_sphere`/`audience_type` 传 `null`(后端已支持,零改动)。弱张力不编码。

**Tech Stack:** Next.js 16 (App Router, React 19), Tailwind v4, Zustand, TypeScript。无测试运行器(项目无前端测试基建)——验证依赖 `npm run build`(含 tsc 类型检查)+ 手动浏览器验证。

**对应 spec:** `docs/superpowers/specs/2026-06-17-translation-option-conflicts-design.md`

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `frontend/lib/translation-conflicts.ts` | 冲突规则纯函数(唯一真相源) | 新建 |
| `frontend/components/workspace/genre-selector.tsx` | 文体选择;读到 `strategy=literal` 时禁用 `brand` | 改 |
| `frontend/components/workspace/strategy-selector.tsx` | 策略选择;读到 `genre=brand` 时禁用 `literal_reference` | 改 |
| `frontend/components/workspace/culture-sphere-selector.tsx` | 文化圈选择;直译模式下整体置灰 + 提示 | 改 |
| `frontend/components/workspace/audience-type-selector.tsx` | 受众选择;直译模式下整体置灰 + 提示 | 改 |
| `frontend/components/workspace/input-panel.tsx` | 发起翻译请求;直译模式下 payload 传 `null` | 改 |

后端零改动(已验证 `cultural_sphere`/`audience_type` 为 `Optional` 且 `None` 时优雅跳过 preprocess)。

---

## Task 1: 新建冲突规则纯函数模块

**Files:**
- Create: `frontend/lib/translation-conflicts.ts`

- [ ] **Step 1: 创建纯函数模块**

写入 `frontend/lib/translation-conflicts.ts`:

```ts
import type { Genre, Strategy } from "@/stores/workspace-store";

/**
 * 直译参考策略的标识。选中该策略 = 纯直译模式,不做文化适配。
 */
export const LITERAL_MODE_STRATEGY: Strategy = "literal_reference";

/**
 * 是否处于纯直译模式。该模式下禁用文化圈/受众选择器,且后端请求
 * 会把 cultural_sphere / audience_type 传 null(后端跳过 preprocess,
 * 不注入 <cultural_constraints> 块,system prompt 自洽)。
 */
export function isLiteralMode(strategy: Strategy): boolean {
  return strategy === LITERAL_MODE_STRATEGY;
}

/**
 * 给定当前策略,返回被禁用的文体。
 * 规则:literal_reference 与 brand(品牌传播)互斥——
 * "最小化适配" 与品牌文体所需的创意本地化方向相反。
 */
export function getDisabledGenres(strategy: Strategy): Genre[] {
  return isLiteralMode(strategy) ? ["brand"] : [];
}

/**
 * 给定当前文体,返回被禁用的策略(规则 1 的反向)。
 * brand 文体下不可选 literal_reference。
 */
export function getDisabledStrategies(genre: Genre): Strategy[] {
  return genre === "brand" ? ["literal_reference"] : [];
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run build`
Expected: `✓ Compiled successfully`,无 TypeScript 错误。

- [ ] **Step 3: 提交**

```bash
git add frontend/lib/translation-conflicts.ts
git commit -m "feat(frontend): add translation option conflict rules module"
```

---

## Task 2: Genre × Strategy 双向禁用(规则 1)

**Files:**
- Modify: `frontend/components/workspace/genre-selector.tsx`
- Modify: `frontend/components/workspace/strategy-selector.tsx`

- [ ] **Step 1: 改 GenreSelector——读 strategy 禁用 brand**

把 `frontend/components/workspace/genre-selector.tsx` 整体替换为:

```tsx
"use client";

import { Genre, useWorkspaceStore } from "@/stores/workspace-store";
import { getDisabledGenres } from "@/lib/translation-conflicts";

const GENRES: { value: Genre; label: string }[] = [
  { value: "political", label: "政治话语" },
  { value: "news", label: "新闻稿" },
  { value: "policy", label: "政策文件" },
  { value: "brand", label: "品牌传播" },
];

export function GenreSelector() {
  const genre = useWorkspaceStore((s) => s.input.genre);
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setGenre = useWorkspaceStore((s) => s.setGenre);
  const disabledGenres = getDisabledGenres(strategy);

  return (
    <div className="flex gap-1.5">
      {GENRES.map((g) => {
        const disabled = disabledGenres.includes(g.value);
        return (
          <button
            key={g.value}
            onClick={() => { if (!disabled) setGenre(g.value); }}
            disabled={disabled}
            title={disabled ? "与当前翻译策略（直译参考）冲突，不可选" : undefined}
            className={`rounded px-2.5 py-1 text-xs transition-all duration-200 border-l-2 ${
              disabled
                ? "opacity-50 cursor-not-allowed bg-muted text-muted-foreground border-l-transparent"
                : genre === g.value
                  ? "cursor-pointer active:scale-[0.95] bg-teal-lightest text-teal border-l-teal font-medium"
                  : "cursor-pointer active:scale-[0.95] bg-muted text-muted-foreground border-l-transparent hover:bg-teal-lightest hover:text-foreground"
            }`}
          >
            {g.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 改 StrategySelector——读 genre 禁用 literal_reference**

把 `frontend/components/workspace/strategy-selector.tsx` 的 import 区与 `StrategySelector` 函数替换为:

```tsx
"use client";

import { Strategy, useWorkspaceStore } from "@/stores/workspace-store";
import { getDisabledStrategies } from "@/lib/translation-conflicts";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const STRATEGIES: {
  value: Strategy;
  label: string;
  desc: string;
  scenario: string;
}[] = [
  {
    value: "semantic_equivalence",
    label: "信息等值",
    desc: "忠实保留原文语义，准确性优先于可读性",
    scenario: "法律文书、外交文件、学术论文",
  },
  {
    value: "audience_first",
    label: "受众优先",
    desc: "侧重目标受众可读性，必要时重构句式",
    scenario: "宣传材料、营销文案、公共沟通",
  },
  {
    value: "literal_reference",
    label: "直译参考",
    desc: "最小化文化适配，逐句对照原文",
    scenario: "专业翻译辅助、原文逐句核查",
  },
];

export function StrategySelector() {
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const genre = useWorkspaceStore((s) => s.input.genre);
  const setStrategy = useWorkspaceStore((s) => s.setStrategy);
  const disabledStrategies = getDisabledStrategies(genre);

  return (
    <TooltipProvider delay={300}>
      <div className="flex gap-3 text-xs text-muted-foreground">
        {STRATEGIES.map((s) => {
          const disabled = disabledStrategies.includes(s.value);
          return (
            <Tooltip key={s.value}>
              <TooltipTrigger
                render={
                  <label
                    className={`flex items-center gap-1.5 ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                    title={disabled ? "与当前文体（品牌传播）冲突，不可选" : undefined}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 rounded-full border-2 transition-all duration-200 ${
                        strategy === s.value
                          ? "border-teal bg-teal"
                          : "border-muted-foreground/30"
                      }`}
                      onClick={() => { if (!disabled) setStrategy(s.value); }}
                    />
                    <span className="font-heading">{s.label}</span>
                  </label> as React.ReactElement
                }
              />
              <TooltipContent side="bottom" className="w-56 flex-col items-start">
                <p>{s.desc}</p>
                {disabled ? (
                  <p className="text-[11px] text-danger mt-1">与当前文体（品牌传播）冲突，不可选</p>
                ) : (
                  <p className="text-[11px] text-background/60 mt-1">适用：{s.scenario}</p>
                )}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npm run build`
Expected: `✓ Compiled successfully`,无错误。

- [ ] **Step 4: 手动验证双向禁用**

Run: `cd frontend && npm run dev`,打开 `http://localhost:3000`(登录后进入工作台)。
- 选 `信息等值` 策略 → 四个文体按钮全可点。✅
- 切到 `直译参考` 策略 → `品牌传播` 按钮置灰、不可点、悬停显示"与当前翻译策略(直译参考)冲突"。✅
- 把文体切回 `政治话语`,再切到 `品牌传播` 文体 → `直译参考` radio 置灰,其 tooltip 显示"与当前文体(品牌传播)冲突"。✅
- 无法同时处于 `直译参考 + 品牌传播` 状态。✅

- [ ] **Step 5: 提交**

```bash
git add frontend/components/workspace/genre-selector.tsx frontend/components/workspace/strategy-selector.tsx
git commit -m "feat(frontend): disable literal/brand conflict combo bidirectionally"
```

---

## Task 3: 直译模式禁用文化圈/受众选择器(规则 2)

**Files:**
- Modify: `frontend/components/workspace/culture-sphere-selector.tsx`
- Modify: `frontend/components/workspace/audience-type-selector.tsx`

- [ ] **Step 1: 改 CultureSphereSelector——直译模式置灰 + 提示**

把 `frontend/components/workspace/culture-sphere-selector.tsx` 整体替换为:

```tsx
"use client";

import { CulturalSphere, useWorkspaceStore } from "@/stores/workspace-store";
import { isLiteralMode } from "@/lib/translation-conflicts";

const SPHERES: { value: CulturalSphere; label: string; tip: string }[] = [
  { value: "western_english", label: "欧美英语圈", tip: "美国、英国、加拿大、澳大利亚" },
  { value: "european_continental", label: "欧洲大陆", tip: "德国、法国、意大利、北欧" },
  { value: "islamic_middle_east", label: "伊斯兰中东", tip: "沙特、阿联酋、伊朗、埃及" },
  { value: "east_asian_confucian", label: "东亚儒家", tip: "日本、韩国" },
  { value: "latin_american", label: "拉美", tip: "巴西、墨西哥、阿根廷" },
  { value: "russian_sphere", label: "俄语圈", tip: "俄罗斯、中亚" },
  { value: "south_asian", label: "南亚", tip: "印度、巴基斯坦、孟加拉" },
  { value: "african", label: "非洲", tip: "南非、尼日利亚、肯尼亚" },
];

export function CultureSphereSelector() {
  const sphere = useWorkspaceStore((s) => s.input.culturalSphere);
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setSphere = useWorkspaceStore((s) => s.setCulturalSphere);
  const current = SPHERES.find((s) => s.value === sphere) ?? SPHERES[0];
  const literalMode = isLiteralMode(strategy);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span className="shrink-0">文化圈</span>
      <div className={`flex items-center gap-2 ${literalMode ? "opacity-50 pointer-events-none" : ""}`}>
        <select
          value={sphere}
          onChange={(e) => setSphere(e.target.value as CulturalSphere)}
          title={current.tip}
          className="cursor-pointer rounded border border-border bg-white px-2 py-1 text-xs text-foreground transition-all duration-200 active:scale-[0.95]"
        >
          {SPHERES.map((s) => (
            <option key={s.value} value={s.value} title={s.tip}>
              {s.label}
            </option>
          ))}
        </select>
        <span className="text-[11px] text-muted-foreground/70">{current.tip}</span>
      </div>
      {literalMode && (
        <span className="text-[11px] text-muted-foreground">直译参考模式下不进行文化适配</span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 改 AudienceTypeSelector——直译模式置灰 + 提示**

把 `frontend/components/workspace/audience-type-selector.tsx` 整体替换为:

```tsx
"use client";

import { AudienceType, useWorkspaceStore } from "@/stores/workspace-store";
import { isLiteralMode } from "@/lib/translation-conflicts";

const AUDIENCES: { value: AudienceType; label: string; tip: string }[] = [
  { value: "general_public", label: "公众", tip: "简明、故事化、避免术语" },
  { value: "media", label: "媒体", tip: "客观、可引用、Reuters 风格" },
  { value: "government", label: "政府", tip: "正式、精准、政策语言" },
  { value: "academic", label: "学术", tip: "概念完整、引用规范" },
  { value: "business", label: "企业", tip: "数据驱动、商业语言" },
  { value: "diaspora_chinese", label: "海外华人", tip: "文化共鸣 + 当地语境" },
];

export function AudienceTypeSelector() {
  const audience = useWorkspaceStore((s) => s.input.audienceType);
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setAudience = useWorkspaceStore((s) => s.setAudienceType);
  const literalMode = isLiteralMode(strategy);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="shrink-0 text-xs text-muted-foreground">受众</span>
      <div className={`flex flex-wrap items-center gap-1.5 ${literalMode ? "opacity-50 pointer-events-none" : ""}`}>
        {AUDIENCES.map((a) => (
          <button
            key={a.value}
            onClick={() => setAudience(a.value)}
            title={a.tip}
            className={`cursor-pointer rounded-full px-2.5 py-1 text-xs transition-all duration-200 active:scale-[0.95] ${
              audience === a.value
                ? "bg-teal text-white"
                : "bg-muted text-muted-foreground hover:bg-teal-lightest"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      {literalMode && (
        <span className="text-[11px] text-muted-foreground">直译参考模式下不进行文化适配</span>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npm run build`
Expected: `✓ Compiled successfully`,无错误。

- [ ] **Step 4: 手动验证直译模式禁用**

`cd frontend && npm run dev`,工作台:
- 选 `直译参考` 策略 → 文化圈下拉框 + 受众按钮组整体置灰、不可交互,出现提示"直译参考模式下不进行文化适配"。✅
- 切回 `信息等值` 或 `受众优先` → 文化圈/受众恢复可点。✅

- [ ] **Step 5: 提交**

```bash
git add frontend/components/workspace/culture-sphere-selector.tsx frontend/components/workspace/audience-type-selector.tsx
git commit -m "feat(frontend): disable cultural sphere/audience in literal mode"
```

---

## Task 4: InputPanel 直译模式 payload 传 null

**Files:**
- Modify: `frontend/components/workspace/input-panel.tsx`

- [ ] **Step 1: 改 handleTranslate 的 payload**

在 `frontend/components/workspace/input-panel.tsx` 顶部 import 区加一行(在已有 import 后):

```tsx
import { isLiteralMode } from "@/lib/translation-conflicts";
```

把 `handleTranslate` 函数内 `apiClient.post("/api/jobs", {...})` 的 payload 替换为(直译模式下两字段传 null):

```tsx
      const literalMode = isLiteralMode(store.input.strategy);
      const data = await apiClient.post("/api/jobs", {
        source_text: store.input.text,
        genre: store.input.genre,
        strategy: store.input.strategy,
        target_languages: store.languages,
        cultural_sphere: literalMode ? null : store.input.culturalSphere,
        audience_type: literalMode ? null : store.input.audienceType,
      });
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npm run build`
Expected: `✓ Compiled successfully`,无错误。

- [ ] **Step 3: 端到端手动验证**

`cd frontend && npm run dev`,工作台:
- 选 `直译参考` 策略(确认 `品牌传播` 文体被禁用,文化圈/受众已置灰)。
- 粘贴一段中文,选一个目标语言,点"开始转译"。
- 打开浏览器 DevTools → Network → 找到 `POST /api/jobs` 请求 → 查看 Request Payload,确认 `cultural_sphere: null`、`audience_type: null`。✅
- 翻译完成后:右侧输出区**不显示** "文化适配说明" 折叠面板(因后端返回的 `cultural_adaptation` 为 null)。✅
- 切回 `受众优先` 策略 → 文化圈/受众恢复可点且**保留原值**,重新翻译后 payload 两字段恢复正常值、文化适配面板重新出现。✅

- [ ] **Step 4: 提交**

```bash
git add frontend/components/workspace/input-panel.tsx
git commit -m "feat(frontend): send null cultural fields in literal translation mode"
```

---

## 验收(全部完成后整体复核)

- [ ] `npm run build` 通过,无 TS 错误。
- [ ] 不可达到 `直译参考 + 品牌传播` 组合(双向禁用生效)。
- [ ] 直译模式下文化圈/受众选择器置灰且不可交互,提示出现。
- [ ] 直译模式请求 payload 两字段为 `null`,响应无 `cultural_adaptation`。
- [ ] 切换出直译模式后选择器恢复、原值保留。
- [ ] 其余功能(翻译、风险标注、采纳/忽略/回退、复制/导出)不受影响。
