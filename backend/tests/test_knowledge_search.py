"""Integration regressions for the NOX Knowledge Index search path."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import knowledge


class KnowledgeSearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "knowledge.sqlite3"
        self.db_patch = patch.object(knowledge, "DB_PATH", self.db_path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_search_returns_indexed_passage_with_source_metadata(self):
        knowledge.index_text(
            "owner-a",
            title="Render deployment guide",
            text="Deploy NOX to Render using the FastAPI backend and uvicorn.",
            source_type="upload",
            filename="deployment.md",
        )

        result = knowledge.search_knowledge("owner-a", "Render deployment", limit=6)

        self.assertEqual(result["retrieval"], "hybrid_lexical")
        self.assertEqual(result["semantic_embeddings"], "not_configured")
        self.assertEqual(result["count"], 1)
        passage = result["results"][0]
        self.assertEqual(passage["title"], "Render deployment guide")
        self.assertEqual(passage["filename"], "deployment.md")
        self.assertIn("uvicorn", passage["text"])
        self.assertGreater(passage["relevance"], 0)

    def test_search_never_returns_another_owners_document(self):
        knowledge.index_text(
            "owner-a",
            title="Private deployment notes",
            text="Secret project code name cobalt deployment instructions.",
            source_type="upload",
            filename="private.md",
        )
        knowledge.index_text(
            "owner-b",
            title="Public cooking notes",
            text="A simple recipe for tomato soup.",
            source_type="upload",
            filename="cooking.md",
        )

        result = knowledge.search_knowledge("owner-b", "cobalt deployment", limit=10)

        self.assertEqual(result["results"], [])
        self.assertEqual(result["count"], 0)

    def test_semantic_search_can_find_meaning_related_passage(self):
        with patch.object(knowledge, "embed_texts", side_effect=lambda texts: [[1.0, 0.0] for _ in texts]):
            knowledge.index_text(
                "owner-a",
                title="Plant biology",
                text="Photosynthesis converts sunlight into chemical energy.",
                source_type="upload",
                filename="biology.txt",
            )
            result = knowledge.search_knowledge("owner-a", "how plants use sunlight", limit=6)

        self.assertEqual(result["retrieval"], "hybrid_lexical_semantic")
        self.assertEqual(result["semantic_embeddings"], "enabled")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["title"], "Plant biology")
        self.assertGreater(result["results"][0]["semantic_similarity"], 0.9)

    def test_empty_query_returns_no_results(self):
        result = knowledge.search_knowledge("owner-a", "   ")

        self.assertEqual(result["results"], [])
        self.assertEqual(result["count"], 0)

    def test_deleted_source_is_removed_from_search(self):
        indexed = knowledge.index_text(
            "owner-a",
            title="Temporary note",
            text="A unique phrase for deletion verification.",
            source_type="upload",
            filename="temporary.txt",
        )
        source_id = indexed["source"]["id"]
        self.assertEqual(knowledge.search_knowledge("owner-a", "deletion verification")["count"], 1)

        self.assertTrue(knowledge.delete_source("owner-a", source_id))
        self.assertEqual(knowledge.search_knowledge("owner-a", "deletion verification")["count"], 0)


if __name__ == "__main__":
    unittest.main()
