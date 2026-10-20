"""Regression tests for NOX's privacy-first operational brain."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import brain


class BrainMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(brain, "DB_PATH", Path(self.temp.name) / "brain.sqlite3")
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_explicit_memory_is_retrievable_only_for_its_session(self):
        saved = brain.remember("session-a", content="Use pytest before merging NOX backend changes", category="project")
        self.assertTrue(saved["stored"])
        results = brain.retrieve_memories("session-a", "pytest backend changes")
        self.assertEqual(len(results), 1)
        self.assertIn("pytest", results[0]["text"])
        self.assertEqual(brain.retrieve_memories("session-b", "pytest backend changes"), [])

    def test_stale_memory_is_not_retrieved_until_revalidated(self):
        saved = brain.remember("session-a", content="Use the legacy provider endpoint", category="operational")
        memory_id = saved["memory"]["id"]
        brain.review_memory("session-a", memory_id, "mark_stale")
        self.assertEqual(brain.retrieve_memories("session-a", "legacy provider endpoint"), [])
        reviewed = brain.review_memory("session-a", memory_id, "revalidate")
        self.assertFalse(reviewed["stale"])
        self.assertEqual(len(brain.retrieve_memories("session-a", "legacy provider endpoint")), 1)

    def test_duplicate_memory_is_merged_not_duplicated(self):
        brain.remember("session-a", content="Prefer concise Hinglish answers", category="preference")
        duplicate = brain.remember("session-a", content="  Prefer concise Hinglish answers  ", category="preference")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(brain.list_memories("session-a")["count"], 1)

    def test_secrets_are_rejected(self):
        with self.assertRaises(ValueError):
            brain.remember("session-a", content="OPENROUTER_API_KEY=sk-example-secret-value", category="operational")
        with self.assertRaises(ValueError):
            brain.remember("session-a", content="My password is hunter2", category="preference")
        self.assertEqual(brain.list_memories("session-a")["count"], 0)

    def test_temporary_memory_has_maximum_seven_day_retention(self):
        saved = brain.remember("session-a", content="Temporary deploy window", category="temporary", retention_days=365)
        self.assertLessEqual(saved["memory"]["retention_days"], 7)

    def test_disabled_memory_blocks_writes_and_retrieval(self):
        brain.update_settings("session-a", {"enabled": False})
        with self.assertRaises(ValueError):
            brain.remember("session-a", content="Do not store while disabled", category="preference")
        self.assertEqual(brain.retrieve_memories("session-a", "preferences"), [])

    def test_device_discovery_keeps_only_allowlisted_fields(self):
        device = brain.record_device("session-a", "Browser", {
            "platform": "Android", "online": True, "viewport": {"width": 390, "height": 844},
            "file_listing": ["/private/photo.jpg"], "precise_location": "secret address",
            "microphone_available": True
        })
        self.assertIn("platform", device["capabilities"])
        self.assertIn("microphone_available", device["capabilities"])
        self.assertNotIn("file_listing", device["capabilities"])
        self.assertNotIn("precise_location", device["capabilities"])

    def test_outcomes_do_not_claim_verified_learning_automatically(self):
        result = brain.record_outcome("session-a", "build", "build passes", "build failed", "failed", "pytest output")
        self.assertFalse(result["requires_validation_before_memory"])
        result = brain.record_outcome("session-a", "build", "build passes", "build passed", "succeeded", "pytest: 12 passed")
        self.assertTrue(result["requires_validation_before_memory"])
        self.assertEqual(brain.overview("session-a")["counts"]["outcomes"], 2)

    def test_proposal_requires_review_and_is_session_scoped(self):
        proposal = brain.create_proposal("session-a", "Improve retry fallback", "Test provider fallback and rollback.", {
            "kind": "workflow", "validation_plan": "Run tests", "rollback_plan": "Restore previous strategy"
        })
        self.assertEqual(brain.list_proposals("session-b"), [])
        reviewed = brain.review_proposal("session-a", proposal["id"], "rejected")
        self.assertEqual(reviewed["status"], "rejected")

    def test_unverified_lessons_cannot_be_marked_verified(self):
        with self.assertRaises(ValueError):
            brain.remember("session-a", content="A guess about a bug fix", category="experience",
                           source="verified_lesson", verification="unverified", confidence=0.4)


if __name__ == "__main__":
    unittest.main()
