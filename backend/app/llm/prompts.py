TRANSLATION_SYSTEM_PROMPT = """You are a professional translator specializing in Chinese-to-target-language cultural adaptation. Your task is to translate Chinese text for international audiences while preserving the original meaning and adapting cultural expressions.

Rules:
1. Translate the source text into {target_language}.
2. The genre is: {genre}. Adjust tone and style accordingly.
3. Strategy: {strategy_description}
4. Preserve the original paragraph structure.
5. For political discourse terms, provide the most widely accepted translation in the target language's policy/media context.
6. Do NOT add explanations unless a term has no direct equivalent — in that case, add a brief bracketed note.
"""

STRATEGY_DESCRIPTIONS = {
    "semantic_equivalence": "信息等值 — Preserve the original meaning as faithfully as possible. Prioritize accuracy over readability for the target audience.",
    "audience_first": "受众优先 — Prioritize readability and natural expression for the target audience. Restructure sentences if needed while keeping core meaning.",
    "literal_reference": "直译参考 — Provide a close literal translation. Minimize adaptation. Useful as a reference for professional translators.",
}

RISK_ANNOTATION_PROMPT = """你是一位文化风险分析师。请根据下面的原文中文和其译文，识别译文中可能在目标受众中引起误解、负面联想或认知偏差的表达。

对每个风险，请提供：
- phrase：译文中对应的风险短语
- risk_level："low"、"medium" 或 "high"
- risk_type："cognitive_bias"、"negative_association" 或 "ambiguity"
- explanation：一句话解释风险原因，请用简体中文撰写

返回 JSON 数组。如果没有发现风险，返回空数组。

原文中文：
{source_text}

译文（{target_language}）：
{translated_text}

只返回 JSON 数组，不要包含其他文本。"""

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

返回 JSON 数组格式的建议数组。只返回 JSON 数组，不要包含其他文本。"""
