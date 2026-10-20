"""Tests for optional semantic embeddings and graceful lexical fallback."""
import os
import unittest
from unittest.mock import patch

from backend.knowledge_embeddings import cosine_similarity, embed_texts


class KnowledgeEmbeddingsTests(unittest.TestCase):
    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)
        self.assertEqual(cosine_similarity(None, [1.0]), 0.0)

    def test_unconfigured_provider_returns_none_vectors(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(embed_texts(["hello", "world"]), [None, None])

    def test_provider_error_does_not_raise(self):
        with patch.dict(os.environ, {
            "NOX_EMBEDDING_API_KEY": "test-key",
            "NOX_EMBEDDING_MODEL": "test-embedding-model",
        }, clear=True), patch("backend.knowledge_embeddings.httpx.Client") as client:
            client.return_value.__enter__.return_value.post.side_effect = RuntimeError("offline")
            self.assertEqual(embed_texts(["hello"]), [None])


if __name__ == "__main__":
    unittest.main()
