from __future__ import annotations

import os
from collections import OrderedDict
from threading import Lock
from typing import List, Optional

import numpy as np
import requests
from loguru import logger


class E5EmbeddingModel:
    """Embedding client backed by an OpenAI-compatible embeddings endpoint.

    The backend intentionally does not load a local Hugging Face model. This
    keeps model memory and ML runtime dependencies out of the API container;
    LM Studio/OpenRouter (or another compatible endpoint) owns embedding
    inference instead.
    """

    dimension = 1024

    def __init__(self):
        configured_provider = os.getenv("SEARCH_EMBEDDING_PROVIDER", "lmstudio").strip().lower()
        if configured_provider != "lmstudio":
            logger.warning(
                "Only the OpenAI-compatible embedding endpoint is supported; "
                "using lmstudio API mode instead of provider={!r}",
                configured_provider,
            )
        self.provider = "lmstudio"
        self.model_name = os.getenv("SEARCH_EMBEDDING_MODEL", "qwen/qwen3-embedding-4b")
        self.base_url = os.getenv(
            "SEARCH_EMBEDDING_BASE_URL", "http://127.0.0.1:1234/v1"
        ).rstrip("/")
        self.api_key = os.getenv("SEARCH_EMBEDDING_API_KEY", "").strip()
        requested_dimensions = os.getenv("SEARCH_EMBEDDING_REQUEST_DIMENSIONS", "").strip()
        try:
            self.request_dimensions = int(requested_dimensions) if requested_dimensions else None
            if self.request_dimensions is not None and self.request_dimensions <= 0:
                raise ValueError
        except ValueError:
            logger.warning("Invalid SEARCH_EMBEDDING_REQUEST_DIMENSIONS; omitting it from the request")
            self.request_dimensions = None
        try:
            self.request_timeout = float(os.getenv("SEARCH_EMBEDDING_TIMEOUT", "60"))
        except ValueError:
            logger.warning("Invalid SEARCH_EMBEDDING_TIMEOUT; using 60 seconds")
            self.request_timeout = 60.0
        self._query_cache = OrderedDict()
        self._cache_lock = Lock()

    @property
    def device_name(self) -> str:
        return "embedding-api"

    @property
    def is_gpu(self) -> bool:
        return False

    def encode(self, texts: List[str], kind: str = "query") -> Optional[np.ndarray]:
        if not texts:
            return None
        prefix = "query: " if kind == "query" else "passage: "
        prepared = [prefix + (text or "") for text in texts]
        return self._encode_api(prepared)

    def _encode_api(self, texts: List[str]) -> Optional[np.ndarray]:
        endpoint = self.base_url if self.base_url.endswith("/embeddings") else f"{self.base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model_name, "input": texts}
        if self.request_dimensions is not None:
            payload["dimensions"] = self.request_dimensions
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            data = response.json().get("data", [])
            ordered = sorted(data, key=lambda item: item.get("index", 0))
            vectors = np.asarray([item["embedding"] for item in ordered], dtype="float32")
            if vectors.ndim != 2 or vectors.shape != (len(texts), self.dimension):
                raise ValueError(
                    f"expected {len(texts)} vectors with {self.dimension} dimensions, got {vectors.shape}"
                )
            if not np.all(np.isfinite(vectors)):
                raise ValueError("Embedding API returned a non-finite embedding")
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if np.any(norms == 0):
                raise ValueError("Embedding API returned a zero-length embedding")
            return (vectors / norms).astype("float32")
        except (requests.RequestException, AttributeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(f"Semantic search disabled; embedding API request failed: {exc}")
            return None

    def encode_query(self, text: str):
        with self._cache_lock:
            cached = self._query_cache.get(text)
            if cached is not None:
                self._query_cache.move_to_end(text)
                return cached
        result = self.encode([text], kind="query")
        if result is None:
            # Do not cache transient embedding API failures.
            return None
        vector = result[0]
        with self._cache_lock:
            self._query_cache[text] = vector
            self._query_cache.move_to_end(text)
            if len(self._query_cache) > 512:
                self._query_cache.popitem(last=False)
        return vector


embedding_model = E5EmbeddingModel()
