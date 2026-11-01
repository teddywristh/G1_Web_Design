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

            self.client = OpenAI(api_key=settings.openai_api_key)
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
        return response.choices[0].message.content or ""
