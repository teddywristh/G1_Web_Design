from collections.abc import Sequence

from app.core.config import Settings
from app.schemas.rag import StoredChunk


class OpenAIService:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        if client is not None:
            self.client = client
        elif settings.openai_api_key:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.ai_request_timeout_seconds,
                max_retries=0,
            )
        else:
            self.client = None

    def _require_client(self) -> None:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self._require_client()
        response = self.client.embeddings.create(
            model=self.settings.default_embedding_model,
            input=list(texts),
        )
        return [item.embedding for item in response.data]

    def answer(self, question: str, chunks: Sequence[StoredChunk]) -> str:
        self._require_client()
        context = "\n\n".join(f"[{index}] {chunk.text}" for index, chunk in enumerate(chunks, 1))
        response = self.client.chat.completions.create(
            model=self.settings.default_llm_model,
            temperature=0,
            max_completion_tokens=self.settings.ai_max_output_tokens,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý pháp lý. Chỉ trả lời dựa trên nội dung nguồn. "
                        "Nếu nguồn không đủ, hãy nói rõ là chưa đủ căn cứ. "
                        "Không tự tạo điều luật hoặc trích dẫn."
                    ),
                },
                {"role": "user", "content": f"Câu hỏi: {question}\n\nNguồn:\n{context}"},
            ],
        )
        from app.core.errors import APIError

        if not response.choices or response.choices[0].finish_reason != "stop":
            raise APIError(502, "ai_incomplete", "The AI response did not finish")
        content = response.choices[0].message.content
        if not content:
            raise APIError(502, "ai_incomplete", "The AI provider returned no answer")
        return content


class AnthropicService:
    """Claude Messages adapter. Fixed endpoint; credentials never become response text."""

    def __init__(self, settings, api_key, model=None, transport=None):
        self.settings = settings
        self.api_key = api_key
        self.model = model or settings.anthropic_model
        self.transport = transport

    def answer(self, question, chunks):
        import httpx

        from app.core.errors import APIError

        if not self.model:
            raise APIError(
                503, "ai_model_required", "Select a Claude API model for this connection"
            )
        context = "\n\n".join(f"[{index}] {chunk.text}" for index, chunk in enumerate(chunks, 1))
        try:
            with httpx.Client(
                timeout=self.settings.ai_request_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": self.settings.anthropic_api_version,
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": self.settings.ai_max_output_tokens,
                        "system": "Bạn là trợ lý pháp lý. Chỉ trả lời dựa trên nguồn. Nếu không đủ căn cứ, hãy nói rõ. Không tự tạo điều luật hoặc trích dẫn.",
                        "messages": [
                            {"role": "user", "content": f"Câu hỏi: {question}\n\nNguồn:\n{context}"}
                        ],
                    },
                )
            if response.status_code in (401, 403):
                raise APIError(
                    502, "ai_authentication_failed", "The AI provider rejected the selected key"
                )
            if response.status_code == 429:
                raise APIError(429, "ai_rate_limited", "The AI provider usage limit was reached")
            if response.status_code >= 400:
                raise APIError(
                    502, "ai_provider_error", "The AI provider could not complete the request"
                )
            result = response.json()
            if result.get("stop_reason") not in ("end_turn", "stop_sequence"):
                raise APIError(
                    502, "ai_incomplete", "The AI response did not finish; try a shorter question"
                )
            answer = "\n".join(
                block["text"]
                for block in result.get("content", [])
                if block.get("type") == "text" and isinstance(block.get("text"), str)
            )
            if not answer.strip():
                raise ValueError("Empty response")
            return answer
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise APIError(503, "ai_unavailable", "The AI provider is unavailable") from None
