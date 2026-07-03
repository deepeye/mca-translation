import json
import httpx
from app.core.config import settings


class BailianClient:
    """Client for Alibaba Cloud Bailian (DashScope compatible) API."""

    def __init__(self):
        self.base_url = settings.BAILIAN_BASE_URL
        self.api_key = settings.BAILIAN_API_KEY

    async def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return {"content": data["choices"][0]["message"]["content"]}

    async def chat_stream(self, model: str, messages: list[dict], temperature: float = 0.3):
        """Yield streaming chunks from Bailian API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

    async def embed(self, texts: list[str], model: str = "text-embedding-v3") -> list[list[float]]:
        """Call DashScope embedding API. Returns list of embedding vectors."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": {
                "texts": texts,
            },
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/embeddings", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            embeddings = []
            for item in data.get("output", {}).get("embeddings", []):
                embeddings.append(item["embedding"])
            return embeddings


bailian_client = BailianClient()
