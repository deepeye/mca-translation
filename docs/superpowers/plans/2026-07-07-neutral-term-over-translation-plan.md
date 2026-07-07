# 中性通用词过翻译修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复“信息等值 + 欧美英语圈”模式下普通词汇“国家”被过译为“the U.S. government and its agencies”的问题。

**Architecture:** 通过两条轻量改动实现：一是弱化 `cultural_profiles.py` 中欧美英语圈画像的强指令语气；二是在 `translation.py` 的 system prompt 构建逻辑里，当策略为 `semantic_equivalence` 时追加“中性通用词保护”显式约束。所有改动均通过 prompt 级单元测试和 LLM 调用 mock 集成测试验证。

**Tech Stack:** Python 3.12, FastAPI, pytest, unittest.mock

## Global Constraints

- 仅修改后端 Python 文件，不改前端、数据库、Docker 配置。
- 所有代码注释保持中英双语，匹配项目现有风格。
- 测试必须能在本地独立运行，不依赖真实 LLM 调用。
- 每次 task 完成后单独提交，commit message 遵循 `fix(backend): ...` 或 `test(backend): ...`。

---

## File Structure

| 文件 | 责任 |
|---|---|
| `backend/app/llm/cultural_profiles.py` | 存储文化圈画像常量，本次弱化 `western_english` 描述 |
| `backend/app/services/translation.py` | 构建主翻译 system prompt，本次追加策略感知约束 |
| `backend/tests/test_cultural_profiles.py` | 验证文化圈画像常量的完整性及文案变更 |
| `backend/tests/test_translation_prompt.py` | 新增：验证 system prompt 构建逻辑和 LLM 调用内容 |

---

### Task 1: 弱化欧美英语圈画像中的强指令

**Files:**
- Modify: `backend/app/llm/cultural_profiles.py:8-12`
- Test: `backend/tests/test_cultural_profiles.py`

**Interfaces:**
- Consumes: 无
- Produces: `CULTURAL_SPHERE_PROFILES["western_english"]` 的字符串内容不再包含“天然警惕”

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_cultural_profiles.py` 末尾追加：

```python
def test_western_english_profile_avoids_over_adaptive_language():
    """欧美英语圈画像不应包含可能诱导模型过度特指翻译的强指令词汇。"""
    profile = CULTURAL_SPHERE_PROFILES["western_english"]
    assert "天然警惕" not in profile
    assert "通常需要更多具体语境才能接受" in profile
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/felixwang/devspace/cc-project/mca-translation/backend
pytest tests/test_cultural_profiles.py::test_western_english_profile_avoids_over_adaptive_language -v
```

Expected: FAIL with `AssertionError: assert '天然警惕' not in ...`

- [ ] **Step 3: 最小实现**

修改 `backend/app/llm/cultural_profiles.py` 中 `western_english` 条目：

```python
    "western_english": (
        "欧美英语圈（美国、英国、加拿大、澳大利亚）：受众秉持个人主义价值观与自由市场语境，"
        "对'国家主导/政府主导'类叙事通常需要更多具体语境才能接受；偏好以数据、案例、个人故事为载体的论证；"
        "倾向直接、简洁、可质疑的表达。"
    ),
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd /Users/felixwang/devspace/cc-project/mca-translation/backend
pytest tests/test_cultural_profiles.py::test_western_english_profile_avoids_over_adaptive_language -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/llm/cultural_profiles.py backend/tests/test_cultural_profiles.py
git commit -m "fix(backend): soften western_english profile to reduce over-adaptation"
```

---

### Task 2: 在信息等值策略下追加中性通用词保护约束

**Files:**
- Modify: `backend/app/services/translation.py:65-81`
- Test: `backend/tests/test_translation_prompt.py`（新建）

**Interfaces:**
- Consumes: `build_translation_system_prompt(..., strategy="semantic_equivalence", ...)`
- Produces: 当 `strategy == "semantic_equivalence"` 时，返回的 system prompt 包含 `[翻译策略约束]` 段

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_translation_prompt.py`：

```python
"""Tests for translation system prompt construction."""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.translation import build_translation_system_prompt, TranslationPipeline


def test_prompt_includes_neutral_term_constraint_for_semantic_equivalence():
    """信息等值策略下应注入中性通用词保护约束。"""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "[翻译策略约束]" in prompt
    assert "当前为信息等值模式" in prompt
    assert "普通政治/国家类通用词汇" in prompt


def test_prompt_excludes_neutral_term_constraint_for_audience_first():
    """受众优先策略下不应注入该约束。"""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="audience_first",
        cultural_sphere="western_english",
        audience_type="general_public",
    )
    assert "[翻译策略约束]" not in prompt
    assert "当前为信息等值模式" not in prompt


def test_prompt_excludes_constraint_when_no_cultural_sphere():
    """未选择文化圈时自然也不应出现该约束。"""
    prompt = build_translation_system_prompt(
        target_language="en-GB",
        genre="political",
        strategy="semantic_equivalence",
    )
    assert "[翻译策略约束]" not in prompt


@pytest.mark.asyncio
async def test_main_translation_sends_constraint_to_llm_for_semantic_equivalence():
    """验证真正发往 LLM 的 system prompt 包含约束。"""
    pipeline = TranslationPipeline()
    with patch("app.services.translation.bailian_client.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"content": "The country plays an important role."}
        await pipeline._main_translation(
            source_text="国家发挥着重要作用。",
            genre="political",
            strategy="semantic_equivalence",
            target_language="en-GB",
            cultural_sphere="western_english",
            audience_type="general_public",
        )
        messages = mock_chat.call_args.kwargs["messages"]
        system_prompt = messages[0]["content"]
        assert "当前为信息等值模式" in system_prompt
        assert "普通政治/国家类通用词汇" in system_prompt


@pytest.mark.asyncio
async def test_main_translation_omits_constraint_for_audience_first():
    """验证受众优先策略下发往 LLM 的 system prompt 不包含约束。"""
    pipeline = TranslationPipeline()
    with patch("app.services.translation.bailian_client.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"content": "translated text"}
        await pipeline._main_translation(
            source_text="国家发挥着重要作用。",
            genre="political",
            strategy="audience_first",
            target_language="en-GB",
            cultural_sphere="western_english",
            audience_type="general_public",
        )
        messages = mock_chat.call_args.kwargs["messages"]
        system_prompt = messages[0]["content"]
        assert "当前为信息等值模式" not in system_prompt
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /Users/felixwang/devspace/cc-project/mca-translation/backend
pytest tests/test_translation_prompt.py -v
```

Expected: 5 tests FAIL，错误为 `AssertionError: assert '[翻译策略约束]' in prompt` 等。

- [ ] **Step 3: 最小实现**

修改 `backend/app/services/translation.py`，在 `build_translation_system_prompt` 函数的 `parts` 列表追加 `</cultural_constraints>` 之前插入：

```python
        if strategy == "semantic_equivalence":
            parts.append(
                "[翻译策略约束]\n"
                "当前为信息等值模式：普通政治/国家类通用词汇（如“国家”“政府”“人民”）应保持中性译法，"
                "仅在原文明确指向特定国家、政府或机构时才具体化。"
            )
```

完整上下文应如下（第 65-83 行）：

```python
        parts = ["<cultural_constraints>"]
        parts.append(f"[文化圈特征] {sphere_profile}")
        if audience_guideline:
            parts.append(f"[受众类型] {audience_guideline}")
        if must_lines:
            parts.append("[术语约束 - 必须遵守]")
            parts.extend(must_lines)
        if suggest_lines:
            parts.append("[术语约束 - 建议遵守]")
            parts.extend(suggest_lines)
        if notes:
            parts.append("[文化注意事项]")
            parts.extend(f"- {n}" for n in notes)
        if taboos:
            parts.append("[禁忌提醒]")
            parts.extend(f"- {t}" for t in taboos)
        if strategy == "semantic_equivalence":
            parts.append(
                "[翻译策略约束]\n"
                "当前为信息等值模式：普通政治/国家类通用词汇（如“国家”“政府”“人民”）应保持中性译法，"
                "仅在原文明确指向特定国家、政府或机构时才具体化。"
            )
        parts.append("</cultural_constraints>")
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd /Users/felixwang/devspace/cc-project/mca-translation/backend
pytest tests/test_translation_prompt.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/translation.py backend/tests/test_translation_prompt.py
git commit -m "fix(backend): add semantic-equivalence guard for neutral political terms"
```

---

## Self-Review

**1. Spec coverage:**

| 设计文档要求 | 对应 Task |
|---|---|
| 弱化 `western_english` 画像 | Task 1 |
| 信息等值策略下追加中性通用词约束 | Task 2 |
| 验证 prompt 构建 | Task 2 Step 1-4 |
| 验证真实 LLM 调用内容 | Task 2 Step 1-4 |

**2. Placeholder scan:** 无 TBD、TODO、未指定代码。

**3. Type consistency:** 所有函数签名沿用现有 `build_translation_system_prompt` 和 `TranslationPipeline._main_translation`，无新增类型。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-07-neutral-term-over-translation-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
