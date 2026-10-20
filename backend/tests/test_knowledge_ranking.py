"""Regression tests for NOX knowledge relevance ranking."""
import unittest
from backend.knowledge_ranking import rank_knowledge_candidates


class KnowledgeRankingTests(unittest.TestCase):
    def test_title_and_phrase_relevance_boost(self):
        rows = [
            {"chunk_id": "a", "title": "Other notes", "content": "Render is mentioned here.", "updated_at": "2026-10-20"},
            {"chunk_id": "b", "title": "Render deployment guide", "content": "Deploy NOX to Render with uvicorn.", "updated_at": "2026-10-19"},
        ]
        ranked = rank_knowledge_candidates("Render deployment", rows)
        self.assertEqual(ranked[0]["chunk_id"], "b")

    def test_irrelevant_candidates_are_excluded(self):
        rows = [
            {"chunk_id": "a", "title": "Cooking", "content": "A recipe for pasta."},
            {"chunk_id": "b", "title": "NOX setup", "content": "Start the backend with uvicorn."},
        ]
        ranked = rank_knowledge_candidates("uvicorn backend", rows)
        self.assertEqual([row["chunk_id"] for row in ranked], ["b"])

    def test_mixed_script_tokens_are_supported(self):
        rows = [
            {"chunk_id": "a", "title": "Hindi note", "content": "NOX को Render पर deploy करें।"},
        ]
        ranked = rank_knowledge_candidates("Render deploy", rows)
        self.assertEqual(ranked[0]["chunk_id"], "a")


if __name__ == "__main__":
    unittest.main()
