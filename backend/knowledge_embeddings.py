"""Optional OpenAI-compatible embeddings for Knowledge Index."""
import logging
import math
import os
import httpx

logger = logging.getLogger("nox.knowledge_embeddings")


def embedding_is_configured():
    return bool(os.getenv("NOX_EMBEDDING_API_KEY", "").strip() and os.getenv("NOX_EMBEDDING_MODEL", "").strip())


def embed_texts(texts):
    if not texts:
        return []
    key = os.getenv("NOX_EMBEDDING_API_KEY", "").strip()
    model = os.getenv("NOX_EMBEDDING_MODEL", "").strip()
    if not key or not model:
        return [None] * len(texts)
    base = os.getenv("NOX_EMBEDDING_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    result = [None] * len(texts)
    try:
        with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
            for start in range(0, len(texts), 32):
                batch = texts[start:start + 32]
                response = client.post(base + "/embeddings",
                    headers={"Authorization": "Bearer " + key},
                    json={"model": model, "input": batch})
                response.raise_for_status()
                for item in response.json().get("data", []):
                    index = int(item.get("index", -1))
                    vector = item.get("embedding")
                    if 0 <= index < len(batch) and isinstance(vector, list) and vector:
                        values = [float(v) for v in vector]
                        if all(math.isfinite(v) for v in values):
                            result[start + index] = values
    except Exception as exc:
        logger.warning("Embedding provider unavailable; lexical fallback (%s)", type(exc).__name__)
    return result


def cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    ln = math.sqrt(sum(a * a for a in left))
    rn = math.sqrt(sum(b * b for b in right))
    if not ln or not rn:
        return 0.0
    return max(0.0, min(1.0, dot / (ln * rn)))
