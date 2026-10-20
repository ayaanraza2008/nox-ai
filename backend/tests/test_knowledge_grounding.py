import unittest

from backend.main import build_chat_messages


class KnowledgeGroundingPromptTests(unittest.TestCase):
    def test_indexed_evidence_has_stable_citation_metadata(self):
        messages = build_chat_messages(
            "What does the project spec say?",
            "en",
            [],
            knowledge_context=[{
                "title": "Project Spec",
                "filename": "spec.md",
                "source_type": "upload",
                "source_id": "source-123",
                "chunk_index": 2,
                "text": "The project uses a FastAPI backend.",
            }],
        )
        grounding = next(item["content"] for item in messages if item["role"] == "system" and "NOX KNOWLEDGE GROUNDING POLICY" in item["content"])
        self.assertIn("[E1]", grounding)
        self.assertIn("Project Spec", grounding)
        self.assertIn("spec.md", grounding)
        self.assertIn("chunk=2", grounding)
        self.assertIn("Do not invent sources", grounding)

    def test_duplicate_passages_are_not_repeated(self):
        duplicate = {
            "title": "Project Spec",
            "filename": "spec.md",
            "source_type": "upload",
            "text": "The project uses a FastAPI backend.",
        }
        messages = build_chat_messages("What backend?", "en", [], knowledge_context=[duplicate, duplicate])
        grounding = next(item["content"] for item in messages if item["role"] == "system" and "NOX KNOWLEDGE GROUNDING POLICY" in item["content"])
        self.assertEqual(grounding.count("The project uses a FastAPI backend."), 1)
        self.assertIn("[E1]", grounding)
        self.assertNotIn("[E2]", grounding)

    def test_saved_memory_is_not_misrepresented_as_public_source(self):
        messages = build_chat_messages(
            "What do I prefer?",
            "en",
            [],
            knowledge_context=[{"category": "preference", "content": "Prefers Hinglish answers.", "source": "user"}],
        )
        grounding = next(item["content"] for item in messages if item["role"] == "system" and "NOX KNOWLEDGE GROUNDING POLICY" in item["content"])
        self.assertIn("Saved memory", grounding)
        self.assertIn("personal context, not public-source citations", grounding)


if __name__ == "__main__":
    unittest.main()
