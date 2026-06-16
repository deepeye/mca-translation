import json
import logging

from app.llm.bailian import bailian_client
from app.llm.prompts import SUGGESTION_PROMPT

logger = logging.getLogger(__name__)


class SuggestionService:
    """Generate replacement suggestions for risky expressions."""

    async def generate(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        phrase: str,
        risk_type: str,
        explanation: str,
    ) -> list[dict]:
        prompt = SUGGESTION_PROMPT.format(
            source_text=source_text,
            translated_text=translated_text,
            target_language=target_language,
            phrase=phrase,
            risk_type=risk_type,
            explanation=explanation,
        )
        messages = [{"role": "user", "content": prompt}]
        try:
            result = await bailian_client.chat(model="qwen-plus", messages=messages, temperature=0.1)
            content = result["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            suggestions = json.loads(content)
            if isinstance(suggestions, list):
                return suggestions
            return []
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Suggestion generation parsing failed: {e}")
            return []


suggestion_service = SuggestionService()
