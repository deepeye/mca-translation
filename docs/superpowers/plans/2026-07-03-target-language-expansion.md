# Target Language Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将翻译目标语言从 5 种扩容到 18 种，并完成集中化常量、后端校验、RTL 显示、文化圈亲和、术语库 LLM seeding、提示词 descriptor 优化。

**Architecture:** 后端新增单一事实来源 `app/constants/languages.py`（18 语言元数据表 + `language_descriptor` + 校验谓词），schema 层用 pydantic v2 `field_validator` 校验，6 个 service 在 prompt 格式化边界注入 descriptor（术语库 dict-key 查找保持 raw code）。前端 `lib/languages.ts` 手工镜像，3 处选择器统一 import，两 store 用 `sphereTouched` 标志实现软亲和，译文输出容器加 `dir="auto"`。术语 seeding 脚本 LLM 生成 15 词×13 语种译文到 JSON 数据文件，`hardcoded_glossary.py` 合并加载（手编优先）。

**Tech Stack:** FastAPI, pydantic v2, SQLAlchemy 2.0, python-docx, Next.js, TypeScript, Zustand, vitest。

## Global Constraints

- 18 个 BCP-47 code（逐字）：`en-GB` `de-DE` `ja-JP` `es-ES` `fr-FR` `ru-RU` `ar` `ko-KR` `pt-BR` `sw-KE` `it-IT` `kk-KZ` `th-TH` `ms-MY` `el-GR` `vi-VN` `ur-PK` `hi-IN`
- 阿拉伯语 = `ar`（MSA，地区中性）；葡萄牙语 = `pt-BR`；哈萨克语 `kk-KZ` 钉死西里尔脚本
- RTL 语言仅 `ar` 与 `ur-PK`；其余 LTR
- 亲和映射：`th-TH`/`ms-MY` 为 `None`（无强亲和），`es-ES`→`latin_american`，`kk-KZ`→`russian_sphere`，`ur-PK`/`hi-IN`→`south_asian`，`sw-KE`→`african`，`pt-BR`→`latin_american`，`ar`→`islamic_middle_east`，`ru-RU`→`russian_sphere`，`vi-VN`/`ko-KR`/`ja-JP`→`east_asian_confucian`，`en-GB`→`western_english`，`de-DE`/`fr-FR`/`it-IT`/`el-GR`→`european_continental`
- DB 列 `TranslationResult.language` 为 `String(8)`，最长 code 5 字符，**无需迁移**
- pydantic v2（`from pydantic import field_validator`）；前端测试用 vitest（`globals: true`，但沿用现有文件显式 import 风格）
- 代码注释中英双语；提交到 main 分支
- **澄清（plan-time）**：spec 第 7 节"亲和在 culturalSphere 为 falsy / 语言空→非空时触发"无法直接实现——store 默认 `culturalSphere="western_english"`、`languages=["en-GB"]` 均非空。改用 `sphereTouched` 标志位：用户手动设过 sphere 或从历史加载后置 true，亲和仅在 `!sphereTouched` 时更新。这更稳健地实现"软提示、不覆盖用户显式选择"的意图。

---

## File Structure

**Create:**
- `backend/app/constants/languages.py` — 18 语言元数据单一事实来源 + `language_descriptor` + `is_supported_language`
- `backend/tests/test_languages_constants.py` — 常量表与 descriptor 单测
- `frontend/lib/languages.ts` — 后端常量的手工 TS 镜像 + `affinitySphereFor`
- `frontend/stores/__tests__/workspace-store.test.ts` — 亲和逻辑测试
- `frontend/stores/__tests__/review-store.test.ts` — 亲和逻辑测试
- `backend/app/generate_glossary_translations.py` — LLM seeding 脚本（放 app/ 沿用 `seed_glossary.py` 模式，便于测试 import）
- `backend/app/data/glossary_translations_generated.json` — 脚本生成的译文数据
- `backend/tests/test_glossary_seeding.py` — seeding 与合并加载测试

**Modify:**
- `backend/app/schemas/job.py` — 7 处 `field_validator`（target_languages + 6 个 lang 字段）
- `backend/app/schemas/review.py` — `ReviewRequest.target_language` 校验
- `backend/app/schemas/glossary.py` — `GlossarySearchRequest.language` 校验
- `backend/app/api/export.py` — `_ExportDocxRequest.language` 校验
- `backend/app/services/translation.py` — 3 处 prompt 注入 descriptor；import
- `backend/app/services/suggestion.py` — prompt 注入 descriptor
- `backend/app/services/review.py` — 2 处 prompt 注入 descriptor（存储字段保持 raw）
- `backend/app/services/acceptance_scorer.py` — prompt 注入 descriptor（`lang` 参数）
- `backend/app/services/narrative_reframe.py` — 2 处 f-string 注入 descriptor
- `backend/app/services/export_docx.py` — RTL 段落 bidi
- `backend/app/api/glossary.py` — `/detect` 硬编码 list 替换为 `SUPPORTED_LANGUAGE_CODES`
- `backend/app/services/hardcoded_glossary.py` — 合并加载生成译文 + `apply_generated_translations`
- `backend/tests/test_cultural_schemas.py` — 扩展校验测试
- `backend/tests/test_cultural_prompt_injection.py` — 更新 descriptor 断言
- `backend/tests/test_export_docx.py` — RTL bidi 测试
- `frontend/components/workspace/input-panel.tsx` — import LANGUAGES
- `frontend/components/review/review-input-panel.tsx` — import LANGUAGES
- `frontend/components/workspace/language-tabs.tsx` — import LANGUAGE_LABELS
- `frontend/stores/workspace-store.ts` — sphereTouched + 亲和
- `frontend/stores/review-store.ts` — sphereTouched + 亲和
- `frontend/components/workspace/translation-result.tsx` — dir="auto"
- `frontend/components/review/review-result-panel.tsx` — dir="auto"
- `frontend/components/workspace/risk-detail-list.tsx` — dir="auto" 建议文本

---

### Task 1: Backend language constants module

**Files:**
- Create: `backend/app/constants/languages.py`
- Test: `backend/tests/test_languages_constants.py`

**Interfaces:**
- Produces: `SUPPORTED_LANGUAGES: list[LanguageInfo]`、`SUPPORTED_LANGUAGE_CODES: frozenset[str]`、`is_supported_language(code) -> bool`、`get_language(code) -> LanguageInfo | None`、`language_descriptor(code) -> str`。`LanguageInfo` 为 frozen dataclass，字段 `code/label_zh/name_en/script/direction/affinity_sphere`。

- [ ] **Step 1: Write the failing test**

`backend/tests/test_languages_constants.py`:
```python
"""验证目标语言常量表与 descriptor 函数。"""
from app.constants.languages import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_LANGUAGE_CODES,
    get_language,
    is_supported_language,
    language_descriptor,
)


def test_supports_18_languages_including_new_13():
    codes = {lang.code for lang in SUPPORTED_LANGUAGES}
    assert len(codes) == 18
    for code in ["ru-RU", "ar", "ko-KR", "pt-BR", "sw-KE", "it-IT", "kk-KZ",
                 "th-TH", "ms-MY", "el-GR", "vi-VN", "ur-PK", "hi-IN"]:
        assert code in codes, f"missing {code}"
    for code in ["en-GB", "de-DE", "ja-JP", "es-ES", "fr-FR"]:
        assert code in codes


def test_is_supported_language_true_false():
    assert is_supported_language("en-GB") is True
    assert is_supported_language("ar") is True
    assert is_supported_language("xx-XX") is False
    assert is_supported_language("") is False


def test_descriptor_ltr_latin_returns_name_only():
    assert language_descriptor("en-GB") == "English"
    assert language_descriptor("sw-KE") == "Swahili"
    assert language_descriptor("pt-BR") == "Portuguese"


def test_descriptor_rtl_includes_script_and_direction():
    assert language_descriptor("ar") == "Arabic (Arabic script, right-to-left)"
    assert language_descriptor("ur-PK") == "Urdu (Arabic script, right-to-left)"


def test_descriptor_non_latin_ltr_includes_script_only():
    assert language_descriptor("kk-KZ") == "Kazakh (Cyrillic script)"
    assert language_descriptor("hi-IN") == "Hindi (Devanagari script)"
    assert language_descriptor("ja-JP") == "Japanese (Japanese script)"


def test_descriptor_unknown_code_falls_back_to_raw():
    assert language_descriptor("xx-XX") == "xx-XX"


def test_affinity_mapping_for_key_languages():
    assert get_language("ru-RU").affinity_sphere == "russian_sphere"
    assert get_language("ar").affinity_sphere == "islamic_middle_east"
    assert get_language("pt-BR").affinity_sphere == "latin_american"
    assert get_language("hi-IN").affinity_sphere == "south_asian"
    assert get_language("th-TH").affinity_sphere is None
    assert get_language("ms-MY").affinity_sphere is None


def test_rtl_languages_are_exactly_arabic_and_urdu():
    rtl = {lang.code for lang in SUPPORTED_LANGUAGES if lang.direction == "rtl"}
    assert rtl == {"ar", "ur-PK"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_languages_constants.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.constants.languages'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/constants/languages.py`:
```python
"""目标语言常量表 — 单一事实来源。

提供 18 个 BCP-47 目标语言的元数据（中文标签、英文名、脚本、书写方向、
亲和文化圈），供 schema 校验、LLM 提示词 descriptor 注入、前端镜像引用。
更新这里时请同步 frontend/lib/languages.ts（手工镜像）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ISO 15924 脚本码 → 英文显示名（用于 descriptor 提示）
_SCRIPT_NAMES: dict[str, str] = {
    "Latn": "Latin",
    "Cyrl": "Cyrillic",
    "Arab": "Arabic",
    "Hang": "Hangul",
    "Thai": "Thai",
    "Grek": "Greek",
    "Deva": "Devanagari",
    "Jpan": "Japanese",
}


@dataclass(frozen=True)
class LanguageInfo:
    """单个目标语言元数据。"""

    code: str
    label_zh: str
    name_en: str
    script: str
    direction: str  # "ltr" | "rtl"
    affinity_sphere: Optional[str] = None


SUPPORTED_LANGUAGES: list[LanguageInfo] = [
    LanguageInfo("en-GB", "英语(英)", "English", "Latn", "ltr", "western_english"),
    LanguageInfo("de-DE", "德语", "German", "Latn", "ltr", "european_continental"),
    LanguageInfo("ja-JP", "日语", "Japanese", "Jpan", "ltr", "east_asian_confucian"),
    LanguageInfo("es-ES", "西班牙语", "Spanish", "Latn", "ltr", "latin_american"),
    LanguageInfo("fr-FR", "法语", "French", "Latn", "ltr", "european_continental"),
    LanguageInfo("ru-RU", "俄语", "Russian", "Cyrl", "ltr", "russian_sphere"),
    LanguageInfo("ar", "阿拉伯语", "Arabic", "Arab", "rtl", "islamic_middle_east"),
    LanguageInfo("ko-KR", "韩语", "Korean", "Hang", "ltr", "east_asian_confucian"),
    LanguageInfo("pt-BR", "葡萄牙语(巴)", "Portuguese", "Latn", "ltr", "latin_american"),
    LanguageInfo("sw-KE", "斯瓦希里语", "Swahili", "Latn", "ltr", "african"),
    LanguageInfo("it-IT", "意大利语", "Italian", "Latn", "ltr", "european_continental"),
    LanguageInfo("kk-KZ", "哈萨克语", "Kazakh", "Cyrl", "ltr", "russian_sphere"),
    LanguageInfo("th-TH", "泰语", "Thai", "Thai", "ltr", None),
    LanguageInfo("ms-MY", "马来语", "Malay", "Latn", "ltr", None),
    LanguageInfo("el-GR", "希腊语", "Greek", "Grek", "ltr", "european_continental"),
    LanguageInfo("vi-VN", "越南语", "Vietnamese", "Latn", "ltr", "east_asian_confucian"),
    LanguageInfo("ur-PK", "乌尔都语", "Urdu", "Arab", "rtl", "south_asian"),
    LanguageInfo("hi-IN", "印地语", "Hindi", "Deva", "ltr", "south_asian"),
]

SUPPORTED_LANGUAGE_CODES: frozenset[str] = frozenset(lang.code for lang in SUPPORTED_LANGUAGES)

_LANGUAGE_BY_CODE: dict[str, LanguageInfo] = {lang.code: lang for lang in SUPPORTED_LANGUAGES}


def is_supported_language(code: str) -> bool:
    """判断给定 BCP-47 code 是否在支持列表内。"""
    return code in SUPPORTED_LANGUAGE_CODES


def get_language(code: str) -> Optional[LanguageInfo]:
    """按 code 查询语言元数据，不存在返回 None。"""
    return _LANGUAGE_BY_CODE.get(code)


def language_descriptor(code: str) -> str:
    """返回注入 LLM 提示词的人类可读语言描述串。

    - LTR + 拉丁脚本 → 仅英文名（如 "English"、"Swahili"）
    - 非拉丁或 RTL → 英文名 + 脚本/方向提示
      （如 "Arabic (Arabic script, right-to-left)"、"Kazakh (Cyrillic script)"）
    未知 code 回退返回原值（不阻断流程，仅降级提示质量）。
    """
    lang = _LANGUAGE_BY_CODE.get(code)
    if lang is None:
        return code
    if lang.script == "Latn" and lang.direction == "ltr":
        return lang.name_en
    parts: list[str] = []
    script_name = _SCRIPT_NAMES.get(lang.script, lang.script)
    parts.append(f"{script_name} script")
    if lang.direction == "rtl":
        parts.append("right-to-left")
    return f"{lang.name_en} ({', '.join(parts)})"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_languages_constants.py -v`
Expected: PASS（8 tests）

- [ ] **Step 5: Commit**

```bash
git add backend/app/constants/languages.py backend/tests/test_languages_constants.py
git commit -m "feat(languages): add centralized 18-language constants + descriptor"
```

---

### Task 2: Backend schema validation

**Files:**
- Modify: `backend/app/schemas/job.py`、`backend/app/schemas/review.py`、`backend/app/schemas/glossary.py`、`backend/app/api/export.py`
- Test: `backend/tests/test_cultural_schemas.py`（扩展）

**Interfaces:**
- Consumes: `is_supported_language` from Task 1
- Produces: 未知 BCP-47 code 在 8 个字段上触发 `pydantic.ValidationError`（→ FastAPI 422）

- [ ] **Step 1: Write the failing tests**

追加到 `backend/tests/test_cultural_schemas.py` 末尾：
```python
def test_create_job_request_rejects_unknown_language():
    with pytest.raises(ValidationError):
        CreateJobRequest(source_text="x", genre="political", target_languages=["xx-XX"])


def test_create_job_request_accepts_all_18_languages():
    from app.constants.languages import SUPPORTED_LANGUAGE_CODES
    req = CreateJobRequest(
        source_text="x", genre="political",
        target_languages=list(SUPPORTED_LANGUAGE_CODES),
    )
    assert len(req.target_languages) == 18


def test_accept_risk_request_rejects_unknown_lang():
    from app.schemas.job import AcceptRiskRequest
    with pytest.raises(ValidationError):
        AcceptRiskRequest(suggestion="x", lang="xx-XX")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_cultural_schemas.py -v`
Expected: 3 new tests FAIL（无校验，未知 code 被接受）

- [ ] **Step 3: Add validators to job.py**

`backend/app/schemas/job.py` 顶部 import 改为：
```python
from pydantic import BaseModel, Field, field_validator

from app.constants.languages import is_supported_language
```
新增模块级 helper（import 之后、class 之前）：
```python
def _validate_lang_code(code: str) -> str:
    """校验 BCP-47 目标语言 code，未知则抛 ValueError（pydantic 转 422）。"""
    if not is_supported_language(code):
        raise ValueError(f"unsupported target language code: {code}")
    return code
```
`CreateJobRequest` 增加校验方法（class 体内）：
```python
    @field_validator("target_languages")
    @classmethod
    def _check_target_languages(cls, v: list[str]) -> list[str]:
        for code in v:
            _validate_lang_code(code)
        return v
```
为 6 个含 `lang` 字段的 model 各加一个校验方法（`AcceptRiskRequest`、`DismissRiskRequest`、`RevertRiskRequest`、`AcceptAllRequest`、`AcceptanceScoreRequest`、`AcceptanceScoreDeltaRequest`）。每个 class 体内加：
```python
    @field_validator("lang")
    @classmethod
    def _check_lang(cls, v: str) -> str:
        return _validate_lang_code(v)
```

- [ ] **Step 4: Add validator to review.py**

`backend/app/schemas/review.py` import 改为 `from pydantic import BaseModel, Field, field_validator`，加 `from app.constants.languages import is_supported_language`。`ReviewRequest` class 体内加：
```python
    @field_validator("target_language")
    @classmethod
    def _check_target_language(cls, v: str) -> str:
        if not is_supported_language(v):
            raise ValueError(f"unsupported target language code: {v}")
        return v
```

- [ ] **Step 5: Add validator to glossary.py**

`backend/app/schemas/glossary.py` import 改为 `from pydantic import BaseModel, Field, field_validator`，加 `from app.constants.languages import is_supported_language`。`GlossarySearchRequest` class 体内加：
```python
    @field_validator("language")
    @classmethod
    def _check_language(cls, v: str) -> str:
        if not is_supported_language(v):
            raise ValueError(f"unsupported target language code: {v}")
        return v
```

- [ ] **Step 6: Add validator to export.py**

`backend/app/api/export.py` import 改为 `from pydantic import BaseModel, field_validator`，加 `from app.constants.languages import is_supported_language`。`_ExportDocxRequest` class 体内加：
```python
    @field_validator("language")
    @classmethod
    def _check_language(cls, v: str) -> str:
        if not is_supported_language(v):
            raise ValueError(f"unsupported target language code: {v}")
        return v
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_cultural_schemas.py -v`
Expected: PASS（含 3 个新测试 + 既有测试不回归）

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/job.py backend/app/schemas/review.py backend/app/schemas/glossary.py backend/app/api/export.py backend/tests/test_cultural_schemas.py
git commit -m "feat(languages): validate target_language codes in schemas (422 on unknown)"
```

---

### Task 3: Backend prompt descriptor injection

**Files:**
- Modify: `backend/app/services/translation.py`、`suggestion.py`、`review.py`、`acceptance_scorer.py`、`narrative_reframe.py`
- Test: `backend/tests/test_cultural_prompt_injection.py`（更新）

**Interfaces:**
- Consumes: `language_descriptor` from Task 1
- 关键不变量：**术语库 dict-key 查找（`translations[code]`、`retrieve_glossary_terms(language=code)`）保持 raw code**；仅 prompt 格式化处注入 descriptor。`review.py` 中写入 `ReviewResult.target_language` 的存储字段保持 raw。

- [ ] **Step 1: Update the prompt-injection test**

`backend/tests/test_cultural_prompt_injection.py` 第 49 行：
```python
    assert "en-GB" in prompt
```
改为：
```python
    assert "English" in prompt
```
（`build_translation_system_prompt` 现注入 descriptor `"English"` 而非 raw `en-GB`）

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_cultural_prompt_injection.py -v`
Expected: 第一个 test FAIL（prompt 仍含 `en-GB` 不含 `English`）

- [ ] **Step 3: Inject descriptor in translation.py**

`backend/app/services/translation.py` 顶部 import 区（第 9 行后）加：
```python
from app.constants.languages import language_descriptor
```
`build_translation_system_prompt` 内第 33-37 行的 `.format(...)`，把 `target_language=target_language,` 改为：
```python
        target_language=language_descriptor(target_language),
```
`_risk_annotation` 内第 292-294 行的 `.format(...)`，把 `target_language=target_language` 改为：
```python
            target_language=language_descriptor(target_language),
```
`translate_stream` 内第 330-332 行的 `.format(...)`，把 `target_language=target_language,` 改为：
```python
            target_language=language_descriptor(target_language),
```
**不要改动**第 152、157、160、181、271 行（术语库 dict-key 查找，保持 raw `target_language`）。

- [ ] **Step 4: Inject descriptor in suggestion.py**

`backend/app/services/suggestion.py` import 区加 `from app.constants.languages import language_descriptor`。`generate` 内第 22-29 行 `.format(...)`，把 `target_language=target_language,` 改为：
```python
            target_language=language_descriptor(target_language),
```

- [ ] **Step 5: Inject descriptor in review.py（prompt 注入处，存储处保持 raw）**

`backend/app/services/review.py` import 区加 `from app.constants.languages import language_descriptor`。`dual_review` 内第 24-30 行 `.format(...)`，把 `target_language=target_language,` 改为：
```python
            target_language=language_descriptor(target_language),
```
`single_review` 内第 43-48 行 `.format(...)`，同样改为 `target_language=language_descriptor(target_language),`。
**不要改动**第 114、127 行（`ReviewResult` 存储字段，保持 raw）。

- [ ] **Step 6: Inject descriptor in acceptance_scorer.py（注意参数名 lang）**

`backend/app/services/acceptance_scorer.py` import 区加 `from app.constants.languages import language_descriptor`。`_one_sample` 内第 109-115 行 `.format(...)`，把 `target_language=lang,` 改为：
```python
            target_language=language_descriptor(lang),
```

- [ ] **Step 7: Inject descriptor in narrative_reframe.py（f-string）**

`backend/app/services/narrative_reframe.py` import 区加 `from app.constants.languages import language_descriptor`。`_build_analysis_prompt` 方法体首行（`return f"""` 之前）加：
```python
        target_language = language_descriptor(target_language)
```
`_build_preview_prompt` 方法体首行（`return f"""` 之前）同样加：
```python
        target_language = language_descriptor(target_language)
```
（f-string 内 `{target_language}` 不变，引用已重赋值为 descriptor 的局部变量）

- [ ] **Step 8: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: 全部 PASS。若其它测试因 prompt 不再含 raw code 而失败，将其断言改为对应 descriptor（如 `"English"`）。已知需改：仅 `test_cultural_prompt_injection.py:49`。

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/translation.py backend/app/services/suggestion.py backend/app/services/review.py backend/app/services/acceptance_scorer.py backend/app/services/narrative_reframe.py backend/tests/test_cultural_prompt_injection.py
git commit -m "feat(languages): inject human-readable language descriptor into LLM prompts"
```

---

### Task 4: Replace hardcoded language list in /detect

**Files:**
- Modify: `backend/app/api/glossary.py:295`

**Interfaces:**
- Consumes: `SUPPORTED_LANGUAGE_CODES` from Task 1

- [ ] **Step 1: Edit the /detect endpoint**

`backend/app/api/glossary.py` 顶部 import 区加：
```python
from app.constants.languages import SUPPORTED_LANGUAGE_CODES
```
第 295 行：
```python
        for lang in ["en-GB", "de-DE", "ja-JP", "es-ES", "fr-FR"]:
```
改为：
```python
        for lang in SUPPORTED_LANGUAGE_CODES:
```

- [ ] **Step 2: Run backend tests**

Run: `cd backend && pytest tests/test_glossary_rag.py tests/test_hardcoded_glossary.py -v`
Expected: PASS（行为对 5 旧语种不变，新增 13 语种也会尝试查 translations）

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/glossary.py
git commit -m "refactor(glossary): use SUPPORTED_LANGUAGE_CODES in /detect fallback"
```

---

### Task 5: Frontend languages mirror + selectors

**Files:**
- Create: `frontend/lib/languages.ts`、`frontend/lib/__tests__/languages.test.ts`
- Modify: `frontend/components/workspace/input-panel.tsx`、`frontend/components/review/review-input-panel.tsx`、`frontend/components/workspace/language-tabs.tsx`

**Interfaces:**
- Produces (TS): `LANGUAGES: LanguageInfo[]`、`LANGUAGE_LABELS: Record<string,string>`、`affinitySphereFor(code) -> string | null`。`LanguageInfo` 字段 `code/labelZh/nameEn/script/direction/affinitySphere`。

- [ ] **Step 1: Write the failing test**

`frontend/lib/__tests__/languages.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { LANGUAGES, LANGUAGE_LABELS, affinitySphereFor } from "@/lib/languages";

describe("languages mirror", () => {
  it("has 18 languages", () => {
    expect(LANGUAGES).toHaveLength(18);
  });

  it("LANGUAGE_LABELS covers all codes", () => {
    for (const l of LANGUAGES) {
      expect(LANGUAGE_LABELS[l.code]).toBe(l.labelZh);
    }
  });

  it("affinitySphereFor returns expected spheres", () => {
    expect(affinitySphereFor("ru-RU")).toBe("russian_sphere");
    expect(affinitySphereFor("ar")).toBe("islamic_middle_east");
    expect(affinitySphereFor("th-TH")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- languages.test`
Expected: FAIL（模块不存在）

- [ ] **Step 3: Create the mirror**

`frontend/lib/languages.ts`:
```ts
// 手工镜像自 backend/app/constants/languages.py — 修改后请同步两端。

export interface LanguageInfo {
  code: string;
  labelZh: string;
  nameEn: string;
  script: string;
  direction: "ltr" | "rtl";
  affinitySphere: string | null;
}

export const LANGUAGES: LanguageInfo[] = [
  { code: "en-GB", labelZh: "英语(英)", nameEn: "English", script: "Latn", direction: "ltr", affinitySphere: "western_english" },
  { code: "de-DE", labelZh: "德语", nameEn: "German", script: "Latn", direction: "ltr", affinitySphere: "european_continental" },
  { code: "ja-JP", labelZh: "日语", nameEn: "Japanese", script: "Jpan", direction: "ltr", affinitySphere: "east_asian_confucian" },
  { code: "es-ES", labelZh: "西班牙语", nameEn: "Spanish", script: "Latn", direction: "ltr", affinitySphere: "latin_american" },
  { code: "fr-FR", labelZh: "法语", nameEn: "French", script: "Latn", direction: "ltr", affinitySphere: "european_continental" },
  { code: "ru-RU", labelZh: "俄语", nameEn: "Russian", script: "Cyrl", direction: "ltr", affinitySphere: "russian_sphere" },
  { code: "ar", labelZh: "阿拉伯语", nameEn: "Arabic", script: "Arab", direction: "rtl", affinitySphere: "islamic_middle_east" },
  { code: "ko-KR", labelZh: "韩语", nameEn: "Korean", script: "Hang", direction: "ltr", affinitySphere: "east_asian_confucian" },
  { code: "pt-BR", labelZh: "葡萄牙语(巴)", nameEn: "Portuguese", script: "Latn", direction: "ltr", affinitySphere: "latin_american" },
  { code: "sw-KE", labelZh: "斯瓦希里语", nameEn: "Swahili", script: "Latn", direction: "ltr", affinitySphere: "african" },
  { code: "it-IT", labelZh: "意大利语", nameEn: "Italian", script: "Latn", direction: "ltr", affinitySphere: "european_continental" },
  { code: "kk-KZ", labelZh: "哈萨克语", nameEn: "Kazakh", script: "Cyrl", direction: "ltr", affinitySphere: "russian_sphere" },
  { code: "th-TH", labelZh: "泰语", nameEn: "Thai", script: "Thai", direction: "ltr", affinitySphere: null },
  { code: "ms-MY", labelZh: "马来语", nameEn: "Malay", script: "Latn", direction: "ltr", affinitySphere: null },
  { code: "el-GR", labelZh: "希腊语", nameEn: "Greek", script: "Grek", direction: "ltr", affinitySphere: "european_continental" },
  { code: "vi-VN", labelZh: "越南语", nameEn: "Vietnamese", script: "Latn", direction: "ltr", affinitySphere: "east_asian_confucian" },
  { code: "ur-PK", labelZh: "乌尔都语", nameEn: "Urdu", script: "Arab", direction: "rtl", affinitySphere: "south_asian" },
  { code: "hi-IN", labelZh: "印地语", nameEn: "Hindi", script: "Deva", direction: "ltr", affinitySphere: "south_asian" },
];

export const LANGUAGE_LABELS: Record<string, string> = Object.fromEntries(
  LANGUAGES.map((l) => [l.code, l.labelZh]),
);

export function affinitySphereFor(code: string): string | null {
  return LANGUAGES.find((l) => l.code === code)?.affinitySphere ?? null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && pnpm test -- languages.test`
Expected: PASS（3 tests）

- [ ] **Step 5: Update input-panel.tsx**

`frontend/components/workspace/input-panel.tsx`：
- 删除第 16-22 行 `const AVAILABLE_LANGUAGES = [...]`
- 第 14 行 import 后加：`import { LANGUAGES } from "@/lib/languages";`
- 第 115 行 `AVAILABLE_LANGUAGES.map((l) => (` 改为 `LANGUAGES.map((l) => (`
- 第 123 行 `{l.label}` 改为 `{l.labelZh}`

- [ ] **Step 6: Update review-input-panel.tsx**

`frontend/components/review/review-input-panel.tsx`：
- 删除第 7-13 行 `const AVAILABLE_LANGUAGES = [...]`
- 第 5 行 import 后加：`import { LANGUAGES } from "@/lib/languages";`
- 第 130 行 `AVAILABLE_LANGUAGES.map((l) => (` 改为 `LANGUAGES.map((l) => (`
- 第 131 行 `{l.label}` 改为 `{l.labelZh}`

- [ ] **Step 7: Update language-tabs.tsx**

`frontend/components/workspace/language-tabs.tsx`：
- 删除第 5-7 行 `const LANGUAGE_LABELS: Record<string, string> = {...}`
- 第 3 行 import 后加：`import { LANGUAGE_LABELS } from "@/lib/languages";`
- 第 22 行 `{LANGUAGE_LABELS[code] || code}` 不变

- [ ] **Step 8: Run frontend tests + typecheck**

Run: `cd frontend && pnpm test && pnpm exec tsc --noEmit`
Expected: 全部 PASS，无类型错误

- [ ] **Step 9: Commit**

```bash
git add frontend/lib/languages.ts frontend/lib/__tests__/languages.test.ts frontend/components/workspace/input-panel.tsx frontend/components/review/review-input-panel.tsx frontend/components/workspace/language-tabs.tsx
git commit -m "feat(languages): centralize frontend language list + expand to 18"
```

---

### Task 6: Frontend cultural-sphere affinity

**Files:**
- Modify: `frontend/stores/workspace-store.ts`、`frontend/stores/review-store.ts`
- Test: `frontend/stores/__tests__/workspace-store.test.ts`、`frontend/stores/__tests__/review-store.test.ts`

**Interfaces:**
- Consumes: `affinitySphereFor` from Task 5
- Produces: 两 store 新增 `sphereTouched: boolean` 状态；`setCulturalSphere` 置 `sphereTouched: true`；`setLanguages`/`setTargetLanguage` 在 `!sphereTouched` 时按语言亲和填 sphere；`loadFromHistory` 置 `sphereTouched: true`；`reset` 复位为 `false`。

- [ ] **Step 1: Write the failing tests**

`frontend/stores/__tests__/workspace-store.test.ts`:
```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useWorkspaceStore } from "@/stores/workspace-store";

describe("workspace-store language→sphere affinity", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().reset();
  });

  it("fills culturalSphere from language affinity when untouched", () => {
    useWorkspaceStore.getState().setLanguages(["ru-RU"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("russian_sphere");
  });

  it("does not override sphere after user manually sets it", () => {
    useWorkspaceStore.getState().setCulturalSphere("african");
    useWorkspaceStore.getState().setLanguages(["ru-RU"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("african");
  });

  it("no-ops for languages with no affinity (th-TH)", () => {
    useWorkspaceStore.getState().setLanguages(["th-TH"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("western_english");
  });

  it("loadFromHistory marks sphere touched (no re-trigger)", () => {
    useWorkspaceStore.getState().loadFromHistory({
      id: "j1", source_text: "x", genre: "political", strategy: "semantic_equivalence",
      cultural_sphere: "south_asian", audience_type: "media", target_languages: ["hi-IN"],
    });
    useWorkspaceStore.getState().setLanguages(["ru-RU"]);
    expect(useWorkspaceStore.getState().input.culturalSphere).toBe("south_asian");
  });
});
```

`frontend/stores/__tests__/review-store.test.ts`:
```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useReviewStore } from "@/stores/review-store";

describe("review-store language→sphere affinity", () => {
  beforeEach(() => {
    useReviewStore.getState().reset();
  });

  it("fills culturalSphere from language affinity when untouched", () => {
    useReviewStore.getState().setTargetLanguage("ar");
    expect(useReviewStore.getState().culturalSphere).toBe("islamic_middle_east");
  });

  it("does not override sphere after manual set", () => {
    useReviewStore.getState().setCulturalSphere("african");
    useReviewStore.getState().setTargetLanguage("ar");
    expect(useReviewStore.getState().culturalSphere).toBe("african");
  });

  it("no-ops for language with no affinity", () => {
    useReviewStore.getState().setTargetLanguage("ms-MY");
    expect(useReviewStore.getState().culturalSphere).toBe("western_english");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && pnpm test -- workspace-store.test review-store.test`
Expected: FAIL（无亲和逻辑，sphere 保持默认或被无关改变）

- [ ] **Step 3: Add affinity to workspace-store.ts**

`frontend/stores/workspace-store.ts`：
- 第 1 行 import 后加：`import { affinitySphereFor } from "@/lib/languages";`
- `WorkspaceState` interface（第 39-65 行）内加字段：`sphereTouched: boolean;`
- `initialState`（第 76-88 行）内加：`sphereTouched: false,`
- 第 95 行 `setCulturalSphere` 改为：
```ts
  setCulturalSphere: (culturalSphere) =>
    set((s) => ({ input: { ...s.input, culturalSphere }, sphereTouched: true })),
```
- 第 97 行 `setLanguages` 改为：
```ts
  setLanguages: (languages) =>
    set((s) => {
      const next: { languages: string[]; input?: typeof s.input } = { languages };
      if (!s.sphereTouched && languages.length > 0) {
        const affinity = languages
          .map((code) => affinitySphereFor(code))
          .find((a): a is string => a !== null);
        if (affinity) {
          next.input = { ...s.input, culturalSphere: affinity as CulturalSphere };
        }
      }
      return next;
    }),
```
- `loadFromHistory`（第 100-112 行）的 `set({...})` 对象内加 `sphereTouched: true,`（与 `languages` 同级）

- [ ] **Step 4: Add affinity to review-store.ts**

`frontend/stores/review-store.ts`：
- 第 1 行 import 后加：`import { affinitySphereFor } from "@/lib/languages";`
- `ReviewState` interface（第 35-60 行）内加字段：`sphereTouched: boolean;`
- `initialState`（第 62-74 行）内加：`sphereTouched: false,`
- 第 81 行 `setTargetLanguage` 改为：
```ts
  setTargetLanguage: (lang) =>
    set((s) => {
      const next: { targetLanguage: string; culturalSphere?: string } = { targetLanguage: lang };
      const affinity = affinitySphereFor(lang);
      if (!s.sphereTouched && affinity) {
        next.culturalSphere = affinity;
      }
      return next;
    }),
```
- 第 83 行 `setCulturalSphere` 改为：
```ts
  setCulturalSphere: (sphere) => set({ culturalSphere: sphere, sphereTouched: true }),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && pnpm test -- workspace-store.test review-store.test`
Expected: PASS（7 tests）

- [ ] **Step 6: Run full frontend test + typecheck**

Run: `cd frontend && pnpm test && pnpm exec tsc --noEmit`
Expected: 全部 PASS，无类型错误

- [ ] **Step 7: Commit**

```bash
git add frontend/stores/workspace-store.ts frontend/stores/review-store.ts frontend/stores/__tests__/workspace-store.test.ts frontend/stores/__tests__/review-store.test.ts
git commit -m "feat(languages): soft language→cultural-sphere affinity via sphereTouched flag"
```

---

### Task 7: Frontend RTL dir="auto"

**Files:**
- Modify: `frontend/components/workspace/translation-result.tsx`、`frontend/components/review/review-result-panel.tsx`、`frontend/components/workspace/risk-detail-list.tsx`

**Interfaces:**
- 无新接口；纯 JSX 属性添加。`dir="auto"` 让浏览器按译文首字符强方向自动判断 RTL/LTR。

- [ ] **Step 1: Add dir="auto" to translation output**

`frontend/components/workspace/translation-result.tsx` 第 143 行：
```tsx
      <div className="whitespace-pre-wrap">{content}</div>
```
改为：
```tsx
      <div className="whitespace-pre-wrap" dir="auto">{content}</div>
```

- [ ] **Step 2: Add dir="auto" to review output**

`frontend/components/review/review-result-panel.tsx` 第 134 行：
```tsx
      <div className="flex-1 min-h-0 overflow-y-auto rounded-md border border-border bg-white p-3 text-sm leading-relaxed">
```
改为：
```tsx
      <div className="flex-1 min-h-0 overflow-y-auto rounded-md border border-border bg-white p-3 text-sm leading-relaxed" dir="auto">
```

- [ ] **Step 3: Add dir="auto" to risk suggestion text**

`frontend/components/workspace/risk-detail-list.tsx` 第 283 行：
```tsx
              <p className="text-[11px] font-medium text-teal-dark">{s.text}</p>
```
改为：
```tsx
              <p className="text-[11px] font-medium text-teal-dark" dir="auto">{s.text}</p>
```
（`s.text` 是目标语言建议文本，`dir="auto"` 对纯阿拉伯语/乌尔都语建议生效。第 182 行的「已采纳」徽章是中英混合，首字符为中文 LTR，dir="auto" 无视觉变化，故不改。）

- [ ] **Step 4: Run frontend typecheck + tests**

Run: `cd frontend && pnpm exec tsc --noEmit && pnpm test`
Expected: PASS，无回归

- [ ] **Step 5: Commit**

```bash
git add frontend/components/workspace/translation-result.tsx frontend/components/review/review-result-panel.tsx frontend/components/workspace/risk-detail-list.tsx
git commit -m "feat(languages): dir=auto on translated-text containers for RTL (ar/ur)"
```

---

### Task 8: docx export RTL paragraph direction

**Files:**
- Modify: `backend/app/services/export_docx.py`
- Test: `backend/tests/test_export_docx.py`

**Interfaces:**
- Consumes: `get_language` from Task 1
- Produces: RTL 语言（ar/ur-PK）导出的译文段落设 `<w:bidi/>`，LTR 不设。

- [ ] **Step 1: Write the failing tests**

追加到 `backend/tests/test_export_docx.py`（若无合适 import，顶部加 `from io import BytesIO`、`from docx import Document`、`from docx.oxml.ns import qn`）：
```python
def test_docx_rtl_for_arabic_sets_bidi():
    from app.services.export_docx import generate_translation_docx
    data = generate_translation_docx(
        source_text="测试", translated_text="اختبار", risk_annotations=[], language="ar"
    )
    doc = Document(BytesIO(data))
    tr_paras = [p for p in doc.paragraphs if "اختبار" in p.text]
    assert tr_paras, "translation paragraph not found"
    pPr = tr_paras[0]._p.pPr
    assert pPr is not None and pPr.find(qn("w:bidi")) is not None


def test_docx_ltr_for_english_no_bidi():
    from app.services.export_docx import generate_translation_docx
    data = generate_translation_docx(
        source_text="测试", translated_text="test", risk_annotations=[], language="en-GB"
    )
    doc = Document(BytesIO(data))
    tr_paras = [p for p in doc.paragraphs if "test" in p.text]
    assert tr_paras
    pPr = tr_paras[0]._p.pPr
    assert pPr is None or pPr.find(qn("w:bidi")) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_export_docx.py -k bidi -v`
Expected: 第一个 test FAIL（无 bidi 设置）

- [ ] **Step 3: Implement RTL paragraph in export_docx.py**

`backend/app/services/export_docx.py` 顶部 import 区加：
```python
from app.constants.languages import get_language
```
新增 helper（与 `_escape_xml` 同区）：
```python
def _set_rtl(paragraph) -> None:
    """为段落设置 RTL 双向方向（<w:bidi/>）。"""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.append(parse_xml(f'<w:bidi {nsdecls("w")}/>'))
```
在 `generate_translation_docx` 内第 139 行（`para_tr.style = doc.styles["Normal"]` 之后）加：
```python
    # RTL 语言（阿拉伯语/乌尔都语）译文段落设双向方向
    lang_info = get_language(language)
    if lang_info is not None and lang_info.direction == "rtl":
        _set_rtl(para_tr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_export_docx.py -v`
Expected: PASS（含 2 个新测试 + 既有测试不回归）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/export_docx.py backend/tests/test_export_docx.py
git commit -m "feat(export): set RTL paragraph direction for arabic/urdu docx"
```

---

### Task 9: Glossary seeding script + merge loading

**Files:**
- Create: `backend/app/generate_glossary_translations.py`、`backend/tests/test_glossary_seeding.py`
- Modify: `backend/app/services/hardcoded_glossary.py`
- 生成: `backend/app/data/glossary_translations_generated.json`

**Interfaces:**
- 关键：生成译文 JSON 的 value 形状必须为 **hardcoded 存储格式** `{"rendering": str, "alternatives": [str], "notes": str}`（非 DB 的 `preferred`），否则 `get_term_translation` 读 `rendering` 为空被跳过。
- 术语稳定标识 = `source_term`（中文字符串）。
- `hardcoded_glossary.py` 新增 `apply_generated_translations(generated: dict) -> None`，合并优先级：手编 > 生成。
- 脚本放 `backend/app/`（沿用 `seed_glossary.py` 模式，便于测试 import），运行 `cd backend && python -m app.generate_glossary_translations`。

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_glossary_seeding.py`:
```python
"""验证术语 seeding 脚本与合并加载。"""
import asyncio
import json

from app.services.hardcoded_glossary import (
    _HARDCODED_TERMS,
    apply_generated_translations,
    get_term_translation,
)


def _term(source_term):
    return next(t for t in _HARDCODED_TERMS if t.source_term == source_term)


def test_apply_generated_translations_merges_new_language():
    original = {t.source_term: dict(t.translations) for t in _HARDCODED_TERMS}
    try:
        gen = {"五位一体": {"ru-RU": {"rendering": "Пять сфер", "alternatives": [], "notes": "x"}}}
        apply_generated_translations(gen)
        info = get_term_translation(_term("五位一体"), "ru-RU")
        assert info["preferred"] == "Пять сфер"
    finally:
        for t in _HARDCODED_TERMS:
            t.translations = original[t.source_term]


def test_apply_generated_translations_handcurated_wins():
    original = {t.source_term: dict(t.translations) for t in _HARDCODED_TERMS}
    try:
        gen = {"五位一体": {"en-GB": {"rendering": "WRONG", "alternatives": [], "notes": ""}}}
        apply_generated_translations(gen)
        info = get_term_translation(_term("五位一体"), "en-GB")
        assert info["preferred"] == "Five-sphere Overall Plan"
    finally:
        for t in _HARDCODED_TERMS:
            t.translations = original[t.source_term]


class _MockClient:
    def __init__(self, payload):
        self._payload = payload

    async def chat(self, **kwargs):
        return {"content": json.dumps(self._payload)}


def test_generate_for_language_returns_valid_structure():
    from app.generate_glossary_translations import _generate_for_language
    payload = {
        "五位一体": {"rendering": "Пять сфер", "alternatives": ["альт"], "notes": "прим"},
        "一带一路": {"rendering": "Один пояс, один путь", "alternatives": [], "notes": ""},
        "unknown_term": {"rendering": "x", "alternatives": [], "notes": ""},
    }
    out = asyncio.run(_generate_for_language(_MockClient(payload), "ru-RU"))
    assert out["五位一体"]["rendering"] == "Пять сфер"
    assert "unknown_term" not in out  # 非真实术语被过滤
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_glossary_seeding.py -v`
Expected: FAIL（`apply_generated_translations` 与脚本模块不存在）

- [ ] **Step 3: Add merge loading to hardcoded_glossary.py**

`backend/app/services/hardcoded_glossary.py` 顶部 import 区（`from dataclasses import dataclass` 之后）加：
```python
import json
import pathlib
```
在文件末尾（`format_glossary_block` 之后）追加：
```python
_GENERATED_FILE = (
    pathlib.Path(__file__).resolve().parent.parent / "data" / "glossary_translations_generated.json"
)


def apply_generated_translations(generated: dict) -> None:
    """将 LLM 生成的译文合并入内存术语条目。手编译文优先，不被覆盖。

    generated 结构：{source_term: {lang_code: {"rendering": str, "alternatives": [str], "notes": str}}}
    """
    for term in _HARDCODED_TERMS:
        gen = generated.get(term.source_term, {})
        if gen:
            term.translations = {**gen, **term.translations}


def _load_generated_translations() -> dict:
    if not _GENERATED_FILE.exists():
        return {}
    try:
        raw = json.loads(_GENERATED_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(raw, dict) and "translations" in raw:
        return raw["translations"]
    return raw if isinstance(raw, dict) else {}


apply_generated_translations(_load_generated_translations())
```

- [ ] **Step 4: Create the seeding script**

`backend/app/generate_glossary_translations.py`:
```python
"""一次性脚本：用 LLM 为 13 个新目标语言生成 15 个硬编码政治术语的译文。

输出 backend/app/data/glossary_translations_generated.json，供
hardcoded_glossary.py 合并加载。译文为 LLM 生成基线，待人工校对。

运行：cd backend && python -m app.generate_glossary_translations
"""
import asyncio
import json
import logging
import pathlib

from app.constants.languages import SUPPORTED_LANGUAGES, language_descriptor
from app.llm.bailian import bailian_client
from app.services.hardcoded_glossary import _HARDCODED_TERMS

logger = logging.getLogger(__name__)

# 仅生成「现有硬编码译文未覆盖」的语言（en-GB/de-DE 已有手编）。
_EXISTING_CODES = {"en-GB", "de-DE"}
NEW_LANGUAGE_CODES = [lang.code for lang in SUPPORTED_LANGUAGES if lang.code not in _EXISTING_CODES]

OUTPUT_FILE = (
    pathlib.Path(__file__).resolve().parent / "data" / "glossary_translations_generated.json"
)


def _build_prompt(lang_code: str) -> str:
    descriptor = language_descriptor(lang_code)
    term_lines = []
    for term in _HARDCODED_TERMS:
        en_ref = term.translations.get("en-GB", {}).get("rendering", "")
        ref = f"（英译参考：{en_ref}）" if en_ref else ""
        term_lines.append(f"- {term.source_term}{ref}")
    return (
        f"将以下中文政治/文化术语译为 {descriptor}。\n\n"
        "要求：\n"
        "- 每个术语给出 rendering（首选译法）、alternatives（0-2 个备选）、"
        'notes（中文风险备注，说明敏感点/转译建议，可空字符串）。\n'
        "- 只输出 JSON 对象，key 为中文术语原文，"
        'value 为 {"rendering": str, "alternatives": [str], "notes": str}。\n'
        "- 不要输出任何解释或 Markdown 代码块。\n\n"
        "术语列表：\n"
        + "\n".join(term_lines)
    )


def _strip_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


async def _generate_for_language(client, lang_code: str) -> dict:
    """为单个语言生成全部 15 词译文。返回 {source_term: {rendering, alternatives, notes}}。"""
    prompt = _build_prompt(lang_code)
    data = {}
    for attempt in (1, 2):
        try:
            result = await client.chat(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            data = json.loads(_strip_fence(result.get("content") or ""))
            break
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("generate for %s attempt %d failed: %s", lang_code, attempt, e)
            if attempt == 2:
                return {}
    valid = {t.source_term for t in _HARDCODED_TERMS}
    out: dict = {}
    for source_term, entry in data.items():
        if source_term not in valid or not isinstance(entry, dict):
            continue
        rendering = str(entry.get("rendering", "")).strip()
        if not rendering:
            continue
        alternatives = [str(a) for a in entry.get("alternatives", []) if a]
        notes = str(entry.get("notes", ""))
        out[source_term] = {"rendering": rendering, "alternatives": alternatives, "notes": notes}
    return out


async def run(client=None, languages=None) -> dict:
    """生成全部语言的译文。返回 {source_term: {lang_code: {...}}}。client 可注入用于测试。"""
    client = client or bailian_client
    codes = languages or NEW_LANGUAGE_CODES
    result: dict = {}
    for lang_code in codes:
        lang_translations = await _generate_for_language(client, lang_code)
        for source_term, entry in lang_translations.items():
            result.setdefault(source_term, {})[lang_code] = entry
        logger.info("generated %d terms for %s", len(lang_translations), lang_code)
    return result


def write_output(data: dict) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": "LLM 生成的政治术语译文基线，待人工校对。"
        "结构：{source_term: {lang_code: {rendering, alternatives, notes}}}。手编译文优先。",
        "translations": data,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _cli():
    logging.basicConfig(level=logging.INFO)
    data = await run()
    write_output(data)
    total = sum(len(v) for v in data.values())
    print(f"wrote {total} entries to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(_cli())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_glossary_seeding.py -v`
Expected: PASS（3 tests）

- [ ] **Step 6: Run the script to generate the committed data file**

Run: `cd backend && python -m app.generate_glossary_translations`
Expected: 13 次 LLM 调用，输出 `app/data/glossary_translations_generated.json`（约 195 条 entry）。需 Bailian API 可达。若 API 不可用，可暂跳过本步（合并加载在文件缺失时安全降级为空），但本步产出的 JSON 需在 API 可用时补跑并提交。

- [ ] **Step 7: Verify merge loads at runtime**

Run: `cd backend && pytest tests/test_hardcoded_glossary.py -v && python -c "from app.services.hardcoded_glossary import get_term_translation, _term_by_source; print(get_term_translation(_term_by_source['一带一路'], 'ru-RU'))"`
Expected: 若 Step 6 已产出 JSON，第二条打印非空 `preferred`；否则打印空 `{"preferred": "", ...}`（降级，符合预期）。

- [ ] **Step 8: Commit**

```bash
git add backend/app/generate_glossary_translations.py backend/app/services/hardcoded_glossary.py backend/tests/test_glossary_seeding.py backend/app/data/glossary_translations_generated.json
git commit -m "feat(glossary): LLM-seed 13 new-language translations + merge-load (hand-curated wins)"
```

---

### Task 10: Full regression

**Files:** 无（验证性任务）

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && pytest -v`
Expected: 全部 PASS

- [ ] **Step 2: Run full frontend test suite + typecheck + build**

Run: `cd frontend && pnpm test && pnpm exec tsc --noEmit && pnpm build`
Expected: 全部 PASS，build 成功

- [ ] **Step 3: Manual RTL verification（需 dev server + 基础设施）**

启动 `docker compose -f docker-compose.dev.yml up -d` + `cd backend && uvicorn app.main:app --reload` + `cd frontend && pnpm dev`，然后：
1. workspace 选 `ar`（阿拉伯语）翻译，确认译文区右起渲染（`dir="auto"` 生效）
2. 选 `ur-PK`（乌尔都语）翻译，确认 RTL
3. 选 `ru-RU`，确认文化圈自动变为「俄语圈」（亲和生效）
4. 手动改文化圈为「非洲」，再切语言，确认文化圈不被覆盖（sphereTouched 生效）
5. 审校页选 `ar`，确认审校输出 RTL + 文化圈自动「伊斯兰中东」
6. 导出 `ar` 译文的 docx，用 Word 打开确认译文段落右起

Expected: 全部符合预期。若某项不符合，回到对应 Task 修复。

- [ ] **Step 4: Final commit（如有手动验证中发现的修复）**

```bash
git add -A
git commit -m "test(languages): full regression for 18-language expansion"
```
（无修复则跳过本步）

---

## Self-Review Notes

- Spec 覆盖：集中化（T1）✓、校验（T2）✓、descriptor（T3）✓、`/detect` list 替换（T4，澄清：是 `/detect` 非 `/detect-cultural`）✓、前端镜像+选择器（T5）✓、亲和（T6，澄清：用 sphereTouched 替代 spec 的 falsy 触发）✓、RTL 前端（T7）✓、RTL docx（T8）✓、seeding（T9，澄清：脚本放 app/ 非 scripts/；JSON value 用 `rendering` 非 `preferred`）✓、回归（T10）✓。
- 已修正 spec 与代码的不一致：`risk_annotation.py` 不存在（实为 `translation.py:_risk_annotation`）；`/detect-cultural` 无语言 list（实为 `/detect`）；glossary 存储格式 `rendering`。
- 范围外（不做）：DB 迁移、每任务 10 语言上限、全量 UI 镜像、新文化圈、`translations` dict-key 校验、`/meta` 端点、人工逐语言审校。

