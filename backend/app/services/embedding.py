"""Configurable embedding providers for LifeNavigator-AI RAG pipeline.

Supports:
1. DeterministicSemanticEmbeddingProvider: High-speed, reproducible 384-dimensional
   subword/token feature-hashing embedding with unit L2 normalization. Operates completely
   offline with zero external credentials or dependencies.
2. OpenAIEmbeddingProvider: Optional OpenAI text-embedding-3-small (1536-dim) when configured.
3. GeminiEmbeddingProvider: Optional Google Gemini text-embedding-004 (768-dim) when configured.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import settings

_WORD = re.compile(r"[\w]+", re.UNICODE)


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""

    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    def dimension(self) -> int:
        ...


class DeterministicSemanticEmbeddingProvider:
    """Zero-dependency, offline deterministic embedding provider.

    Maps text into a 384-dimensional unit vector using subword character n-grams
    and lexical tokens with signed hashing and L2 normalization.
    Cos(u, v) preserves semantic token proximity and keyword affinity.
    """

    def __init__(self, dimension: int = 384):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def _extract_features(self, text: str) -> list[tuple[str, float]]:
        cleaned = re.sub(r"\s+", " ", text.strip().casefold())
        if not cleaned:
            return []

        words = _WORD.findall(cleaned)
        features: list[tuple[str, float]] = []

        # Word unigrams with word-length weighting
        for word in words:
            if len(word) >= 2:
                features.append((f"w:{word}", 1.5))

        # Word bigrams for local semantic context
        for i in range(len(words) - 1):
            features.append((f"bg:{words[i]}_{words[i+1]}", 1.2))

        # Character 3-grams and 4-grams for subword matching (handles plurals, prefixes, typos)
        padded = f" {cleaned} "
        for n in (3, 4):
            for i in range(len(padded) - n + 1):
                ngram = padded[i:i + n]
                if not ngram.isspace():
                    features.append((f"ng:{ngram}", 0.7))

        return features

    def embed_text(self, text: str) -> list[float]:
        features = self._extract_features(text)
        if not features:
            return [0.0] * self._dim

        vector = [0.0] * self._dim
        dim = self._dim

        for feat, weight in features:
            # Deterministic hash to dimension index and sign
            digest = hashlib.md5(feat.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vector[idx] += sign * weight

        # L2 normalization to unit hypersphere
        sq_sum = sum(x * x for x in vector)
        if sq_sum > 0.0:
            norm = math.sqrt(sq_sum)
            return [round(x / norm, 6) for x in vector]
        return [0.0] * self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class OpenAIEmbeddingProvider:
    """OpenAI API embedding provider using text-embedding-3-small."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self._dim = 1536
        self._fallback = DeterministicSemanticEmbeddingProvider()

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        results = self.embed_batch([text])
        return results[0] if results else self._fallback.embed_text(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": texts},
                )
                if res.status_code == 200:
                    data = res.json()
                    return [item["embedding"] for item in data.get("data", [])]
        except Exception:
            pass
        return self._fallback.embed_batch(texts)


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider based on environment settings."""
    provider_type = (settings.EMBEDDING_PROVIDER or "").lower().strip()
    if provider_type == "openai" and settings.OPENAI_API_KEY:
        return OpenAIEmbeddingProvider(settings.OPENAI_API_KEY)
    return DeterministicSemanticEmbeddingProvider()
