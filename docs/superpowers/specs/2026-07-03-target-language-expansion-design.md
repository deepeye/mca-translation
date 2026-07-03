# 翻译目标语言扩容设计

> 日期：2026-07-03
> 状态：已确认，待写实施计划
> 范围：将翻译目标语言从 5 种扩容到 18 种，并解决现有列表硬编码重复、文化圈/语言解耦、阿拉伯语/乌尔都语 RTL、提示词注入原始 BCP-47 码、术语库新语种空缺等问题。

## 1. 背景与现状

当前支持 5 种目标语言（BCP-47 码 + 中文标签）：

| code | label |
|---|---|
| `en-GB` | 英语(英) |
| `de-DE` | 德语 |
| `ja-JP` | 日语 |
| `es-ES` | 西班牙语 |
| `fr-FR` | 法语 |

现有问题（探查所得）：

1. **无集中常量**：5 语言列表在 4 处硬编码重复——`frontend/components/workspace/input-panel.tsx:16-22`、`frontend/components/review/review-input-panel.tsx:7-13`、`frontend/components/workspace/language-tabs.tsx:5-7`、`backend/app/api/glossary.py:295`。
2. **后端零校验**：`target_language` 端到端为自由字符串，`# BCP-47 codes` 注释是唯一文档。
3. **文化圈与语言完全解耦**：8 文化圈（`backend/app/llm/cultural_profiles.py`）与语言无映射，导致 `russian_sphere` 存在但无 `ru-RU`、`islamic_middle_east` 存在但无 `ar-*`、`south_asian` 存在但无 `hi-IN`/`ur-PK`、`african` 存在但无 `sw-KE`、`latin_american` 存在但只有 `es-ES`。
4. **提示词注入原始 code**：6 个 prompt 模板的 `{target_language}` 占位符直接注入 BCP-47 码（如 "Translate into en-GB"），不转人类可读语言名，无脚本/方向提示。
5. **术语库译文稀疏**：`hardcoded_glossary.py` 15 词仅 `en-GB`（15 条）+ `de-DE`（1 条）；`ja-JP`/`es-ES`/`fr-FR` 均无译文。
6. **DB 列 `TranslationResult.language` 为 `String(8)`**：所有拟新增 code 最长 5 字符，无需迁移。

## 2. 目标

新增 13 语种：俄语、阿拉伯语、韩语、葡萄牙语、斯瓦希里语、意大利语、哈萨克语、泰语、马来语、希腊语、越南语、乌尔都语、印地语。合计 18 种。

完整范围（用户确认）：
- 集中化语言常量（单一事实来源 + 前端镜像）
- 后端校验 target_language
- 阿拉伯语/乌尔都语 RTL 显示
- 文化圈↔语言亲和映射（软提示）
- 新语种术语库 seeding（LLM 生成基线）
- LLM 提示词优化（注入人类可读语言名 + 脚本/方向提示）

## 3. 架构：单一事实来源

```
backend/app/constants/languages.py        ← 单一事实来源（后端）
        │
        ├─→ backend schemas (校验)
        ├─→ backend services/prompts (descriptor 注入)
        ├─→ backend glossary.py:295 (替换硬编码 list)
        │
        └─→ frontend/lib/languages.ts     ← 手工镜像（TS），带 "keep in sync" 注释
                │
                ├─→ input-panel.tsx (workspace 选择器)
                ├─→ review-input-panel.tsx (审校选择器)
                └─→ language-tabs.tsx (标签)
```

**镜像 vs `/meta/languages` API 端点**：采用手工镜像（沿用项目现有模式——文化圈即 `workspace-store.ts` 手工镜像 `cultural_profiles.py`）。`/meta` 端点引入网络往返与加载态，对静态 18 行表为过度设计。代价：两端需手动保持同步（注释标注）。

## 4. 集中式语言表

`backend/app/constants/languages.py`，每条记录 6 字段：

| 字段 | 用途 | 示例 |
|---|---|---|
| `code` | BCP-47，DB/管线键 | `ar` |
| `label_zh` | 前端中文显示标签 | `阿拉伯语` |
| `name_en` | 注入 LLM 提示词的人类可读名 | `Arabic` |
| `script` | ISO 15924 脚本码（驱动提示词脚本提示 + 字体） | `Arab` |
| `direction` | `ltr` / `rtl`（驱动 `dir="auto"` 容器 + docx 段落方向） | `rtl` |
| `affinity_sphere` | 默认亲和文化圈，`None` 表示无强亲和 | `islamic_middle_east` |

### 完整 18 语言表

| code | label_zh | name_en | script | dir | affinity_sphere |
|---|---|---|---|---|---|
| `en-GB` | 英语(英) | English | Latn | ltr | `western_english` |
| `de-DE` | 德语 | German | Latn | ltr | `european_continental` |
| `ja-JP` | 日语 | Japanese | Japn | ltr | `east_asian_confucian` |
| `es-ES` | 西班牙语 | Spanish | Latn | ltr | `latin_american` |
| `fr-FR` | 法语 | French | Latn | ltr | `european_continental` |
| `ru-RU` | 俄语 | Russian | Cyrl | ltr | `russian_sphere` |
| `ar` | 阿拉伯语 | Arabic | Arab | rtl | `islamic_middle_east` |
| `ko-KR` | 韩语 | Korean | Hang | ltr | `east_asian_confucian` |
| `pt-BR` | 葡萄牙语(巴) | Portuguese | Latn | ltr | `latin_american` |
| `sw-KE` | 斯瓦希里语 | Swahili | Latn | ltr | `african` |
| `it-IT` | 意大利语 | Italian | Latn | ltr | `european_continental` |
| `kk-KZ` | 哈萨克语 | Kazakh | Cyrl | ltr | `russian_sphere` |
| `th-TH` | 泰语 | Thai | Thai | ltr | `None` |
| `ms-MY` | 马来语 | Malay | Latn | ltr | `None` |
| `el-GR` | 希腊语 | Greek | Grek | ltr | `european_continental` |
| `vi-VN` | 越南语 | Vietnamese | Latn | ltr | `east_asian_confucian` |
| `ur-PK` | 乌尔都语 | Urdu | Arab | rtl | `south_asian` |
| `hi-IN` | 印地语 | Hindi | Deva | ltr | `south_asian` |

**决策记录**：
- `es-ES` 亲和圈定为 `latin_american`（匹配项目国际传播定位，中国对西语传播主要面向拉美）。
- `th-TH`（东南亚佛教）/`ms-MY`（东南亚穆斯林）无强匹配的现有文化圈，留 `None`，不强行映射以免误导 LLM 文化约束。
- 阿拉伯语用 `ar`（现代标准阿拉伯语 MSA，地区中性），非 `ar-SA`。
- 葡萄牙语用 `pt-BR`（匹配 `latin_american` 文化圈与使用者规模）。
- 哈萨克语 `kk-KZ` 钉死西里尔脚本（哈国正推进拉丁化但当前标准仍为西里尔）。

## 5. 后端校验

`constants/languages.py` 提供：
- `SUPPORTED_LANGUAGE_CODES: frozenset[str]`（18 个 code）
- `is_supported_language(code: str) -> bool`

在以下 schema 字段加 Pydantic `field_validator`，未知 code → 422：
- `CreateJobRequest.target_languages`（`backend/app/schemas/job.py:26`）
- `ReviewRequest.target_language`（`backend/app/schemas/review.py:29`）
- 风险操作请求的 `lang`（`backend/app/schemas/job.py:74,77,81,85,94,100`）
- `backend/app/api/export.py:16` 与 `backend/app/schemas/glossary.py:82` 的 `language` 字段

现有 5 code 全在新表内，旧数据不受影响。**不**校验 glossary `translations` dict 的 key（过度范围）。

## 6. LLM 提示词 descriptor

新增 `language_descriptor(code: str) -> str`（在 `constants/languages.py`）：
- **LTR + Latn** → 仅英文名：`"English"`、`"Swahili"`、`"Portuguese"`
- **非拉丁或 RTL** → 英文名 + 脚本/方向提示：
  - `ar` → `"Arabic (Arabic script, right-to-left)"`
  - `ur-PK` → `"Urdu (Arabic script, right-to-left)"`
  - `hi-IN` → `"Hindi (Devanagari script)"`
  - `kk-KZ` → `"Kazakh (Cyrillic script)"` ← 钉死西里尔，避免哈国拉丁化歧义
  - `ru-RU` → `"Russian (Cyrillic script)"`
  - `th-TH` → `"Thai (Thai script)"`
  - `ko-KR` → `"Korean (Hangul script)"`
  - `el-GR` → `"Greek (Greek script)"`
  - `ja-JP` → `"Japanese (Japanese script)"`

脚本码 → 显示名映射：Latn→Latin、Cyrl→Cyrillic、Arab→Arabic、Hang→Hangul、Thai→Thai、Grek→Greek、Deva→Devanagari、Japn→Japanese。

**注入方式**：`backend/app/llm/prompts.py` 的 `{target_language}` 占位符名不变，只改调用方传值——各 service 在格式化前 `lang_desc = language_descriptor(target_language)`，传 `target_language=lang_desc`。

**关键**：术语库 `translations[code]` 查找仍用原始 code（不传 descriptor）。

涉及 service：
- `backend/app/services/translation.py`（`build_translation_system_prompt` 及管线各节点）
- `backend/app/services/risk_annotation.py`
- `backend/app/services/suggestion.py`
- `backend/app/services/review.py`
- `backend/app/services/acceptance_scorer.py`
- `backend/app/services/narrative_reframe.py`

测试 `backend/tests/test_cultural_prompt_injection.py` 的 `assert "en-GB" in prompt` → 改为 `assert "English" in prompt`。

## 7. 文化圈亲和行为（前端）

`frontend/stores/workspace-store.ts` 与 `frontend/stores/review-store.ts` 加亲和逻辑：

- **触发时机**：仅当语言从「空 → 非空」且 `culturalSphere` 为 falsy 时，取首个有亲和的语言的 `affinity_sphere` 自动填入。
- 已选文化圈 → 不覆盖；从历史加载（`loadFromHistory`）→ sphere 已存，不触发。
- 仅首选项触发，避免「用户手动清空 sphere 后，每次选语言又被填回」的烦扰。

亲和数据从 `frontend/lib/languages.ts` 镜像读取（`LANGUAGES.find(l => l.code === code).affinity_sphere`）。

## 8. RTL 显示

- **前端**：译文输出容器加 `dir="auto"`（浏览器按首字符强方向自动判断），覆盖：
  - workspace 译文区
  - 审校输出
  - 叙事重排预览
  - 风险 Popover 内建议

  UI 框架（按钮/导航/输入）保持 LTR（应用面向中文编辑）。
- **docx 导出**：`backend/app/services/export_docx.py` 按语言 `direction` 设置段落 RTL（python-docx `paragraph_format.bidi = True`）。

## 9. 术语 seeding 脚本

**数据存放**：新生成译文放独立 JSON `backend/app/data/glossary_translations_generated.json`（`{term_key: {lang: {preferred, alternatives, note}}}`），不内联 Python。理由：避免代码生成 Python 源码、便于 diff/审校/重跑。

**脚本**：`backend/scripts/generate_glossary_translations.py`
- 从 `hardcoded_glossary.py` 读取 15 个术语（含中文原文 + 现有 en-GB 译法作参考）
- **按语言批量调用**（13 次 LLM 调用，每次生成该语言全部 15 词的译文 + 中文风险备注），失败重试该语言
- 提示词注入 `language_descriptor(code)`（如「译为 Kazakh (Cyrillic script)」）
- 输出写入 JSON，幂等可重跑

**合并加载**：`hardcoded_glossary.py` import 时加载 JSON 并合并入各 term 的 `translations`。优先级：手编（Python 内 en-GB/de-DE）> 生成（JSON），即 `translations = {**generated, **hand_curated}`，手编不被覆盖。

**质量定位**：LLM 生成译文为基线，脚本 docstring + JSON 顶部注释均标注「LLM 生成，待人工校对」。政治术语译法敏感，后续由领域专家逐语言审校。

## 10. 测试

**后端**
- `test_languages_constants.py`（新）：18 code 齐全、亲和映射正确、`language_descriptor` 输出（`en-GB`→`"English"`、`ar`→`"Arabic (Arabic script, right-to-left)"`、`kk-KZ`→`"Kazakh (Cyrillic script)"`）、`is_supported_language` 真假例
- `test_cultural_schemas.py`（扩展）：`CreateJobRequest(target_languages=["xx-XX"])` 抛校验错；18 code 通过
- `test_cultural_prompt_injection.py`（更新）：断言 descriptor 在 prompt 内
- `test_glossary_seeding.py`（新）：mock LLM，跑脚本，断言 JSON 结构 + 合并入 term 后 `translations["ru-RU"]` 可读

**前端**
- `workspace-store` 亲和测试：`setLanguages(["ru-RU"])` + sphere 空 → sphere 变 `russian_sphere`；sphere 已设 → 不变；再切语言 → 不变
- 语言选择器渲染 18 项；`languages.ts` 与后端表一致

## 11. 范围外（明确不做）

- DB 迁移（`String(8)` 装得下所有 code，`ar` 仅 2 字符）
- 调整每任务最多 10 语言上限
- 全量 RTL UI 镜像（仅 `dir="auto"` + docx bidi）
- 新增文化圈（沿用现有 8 个；`th-TH`/`ms-MY` 留 `None`）
- 校验 glossary `translations` dict key
- `/meta/languages` 端点（用镜像）
- 人工逐语言审校 seeded 译文（仅 LLM 基线）

## 12. 实施顺序（供 writing-plans 参考）

1. 后端 `constants/languages.py`（表 + `language_descriptor` + `is_supported_language`）+ 单测
2. 后端 schema 校验（5 处 field_validator）+ 单测
3. 后端 6 service 注入 descriptor + 替换 `glossary.py:295` 硬编码 list + 更新 prompt 注入测试
4. 前端 `lib/languages.ts` 镜像 + 4 处选择器/标签改 import + 亲和逻辑 + RTL `dir="auto"`
5. docx 导出 RTL 段落方向
6. 术语 seeding 脚本 + JSON 数据文件 + `hardcoded_glossary.py` 合并加载 + 单测
7. 全量回归（后端 pytest + 前端 pnpm test + 手动验证阿拉伯语/乌尔都语 RTL 渲染）
