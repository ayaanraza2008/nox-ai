"""Regression tests for session-scoped NOX knowledge indexing."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import knowledge, main


class KnowledgeIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "knowledge.sqlite3"
        self.db_patch = patch.object(knowledge, "DB_PATH", self.path)
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_index_and_search_returns_source_passages(self):
        indexed = knowledge.index_text(
            "session-a",
            title="NOX deployment guide",
            text="Deploy NOX AI to Render using the backend requirements file and the uvicorn start command.",
            source_type="upload",
            filename="guide.txt",
        )
        result = knowledge.search_knowledge("session-a", "Render uvicorn", 5)
        self.assertEqual(indexed["chunks"], 1)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["title"], "NOX deployment guide")
        self.assertIn("uvicorn", result["results"][0]["text"])

    def test_sources_and_retrieval_are_scoped_by_owner(self):
        knowledge.index_text("session-a", title="Private note", text="secret project code alpha", source_type="upload")
        self.assertEqual(knowledge.list_sources("session-b")["source_count"], 0)
        self.assertEqual(knowledge.search_knowledge("session-b", "secret project alpha")["count"], 0)

    def test_duplicate_content_does_not_create_duplicate_chunks(self):
        first = knowledge.index_text("session-a", title="first.txt", text="same content for deduplication", source_type="upload")
        second = knowledge.index_text("session-a", title="second.txt", text="same content for deduplication", source_type="upload")
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(knowledge.list_sources("session-a")["source_count"], 1)

    def test_delete_removes_source_and_searchable_passages(self):
        item = knowledge.index_text("session-a", title="delete me", text="unique deletion marker zetaomega", source_type="upload")
        self.assertTrue(knowledge.delete_source("session-a", item["source"]["id"]))
        self.assertEqual(knowledge.search_knowledge("session-a", "zetaomega")["count"], 0)
        self.assertFalse(knowledge.delete_source("session-b", item["source"]["id"]))

    def test_text_file_extraction_and_unsupported_extension(self):
        self.assertEqual(knowledge.extract_file_text("notes.txt", b"hello\nworld"), "hello\nworld")
        with self.assertRaises(HTTPException) as error:
            knowledge.extract_file_text("secret.exe", b"binary")
        self.assertEqual(error.exception.status_code, 415)

    def test_private_network_urls_are_rejected(self):
        with self.assertRaises(HTTPException) as error:
            knowledge._validate_public_url("http://127.0.0.1/admin")
        self.assertEqual(error.exception.status_code, 400)

    def test_retrieved_passages_are_added_as_untrusted_evidence(self):
        messages = main.build_chat_messages(
            "How do I deploy?",
            "en",
            [],
            knowledge_context=[{"title": "guide.txt", "filename": "guide.txt", "text": "Use uvicorn to start the backend."}],
        )
        self.assertIn("untrusted source text", messages[1]["content"])
        self.assertIn("Use uvicorn", messages[1]["content"])
        self.assertEqual(messages[-1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
