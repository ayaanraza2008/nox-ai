"""Regression tests for remote browser destination safety."""
import unittest
from backend.browser_automation import BrowserAgent, BrowserAgentError, page_state_changed, unwrap_search_result_url, extractive_summary, shared_source_terms

class BrowserSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_http_scheme(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("file:///etc/passwd")
    async def test_rejects_localhost(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("http://localhost:8000/")
    async def test_rejects_private_ip(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("http://127.0.0.1/")
    async def test_rejects_embedded_credentials(self):
        with self.assertRaises(BrowserAgentError):
            await BrowserAgent()._public_url("https://user:password@example.com/")
    async def test_field_values_are_redacted_from_task_summary(self):
        summary = BrowserAgent()._safe_command_summary("type MySecret123 into the password field")
        self.assertNotIn("MySecret123", summary)
        self.assertIn("[value redacted]", summary)

    async def test_page_state_change_requires_observable_change(self):
        before = {"url": "https://example.com/", "title": "Example", "body_sha256": "same"}
        self.assertFalse(page_state_changed(before, dict(before)))
        self.assertTrue(page_state_changed(before, {**before, "url": "https://example.com/next"}))
        self.assertTrue(page_state_changed(before, {**before, "body_sha256": "changed"}))


    async def test_unwraps_duckduckgo_redirect_to_public_url(self):
        url = unwrap_search_result_url("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs")
        self.assertEqual(url, "https://example.com/docs")

    async def test_search_result_rejects_non_http_urls(self):
        self.assertIsNone(unwrap_search_result_url("javascript:alert(1)"))
        self.assertIsNone(unwrap_search_result_url("https://duckduckgo.com/"))

    async def test_search_result_strips_fragment(self):
        self.assertEqual(unwrap_search_result_url("https://example.com/page#section"), "https://example.com/page")

    async def test_extractive_summary_prefers_topic_relevant_sentences(self):
        text = (
            "Quantum computing systems use quantum bits to represent information and solve selected problems. "
            "Researchers also study quantum error correction to reduce noise in quantum processors. "
            "The local football team won its match after a late goal."
        )
        summary = extractive_summary(text, "quantum computing")
        self.assertTrue(summary)
        self.assertTrue(any("Quantum computing" in sentence for sentence in summary))

    async def test_shared_terms_only_include_terms_present_in_multiple_sources(self):
        sources = [
            {"text": "Quantum processors need error correction and stable hardware."},
            {"text": "Error correction helps quantum processors manage noise."},
            {"text": "Gardening soil needs water and sunlight."},
        ]
        terms = shared_source_terms(sources)
        self.assertIn("quantum", terms)
        self.assertIn("processors", terms)
        self.assertNotIn("gardening", terms)

    async def test_idle_state(self):
        result = await BrowserAgent().state("test-owner")
        self.assertFalse(result["active"])
        self.assertEqual(result["status"], "idle")



class ResearchSynthesisPromptTests(unittest.TestCase):
    def test_synthesis_prompt_requires_evidence_and_disagreement_reporting(self):
        from backend.research_synthesis import build_synthesis_request
        prompt = build_synthesis_request("quantum computing", [
            {"title": "Source A", "url": "https://example.com/a", "text": "A source excerpt."},
            {"title": "Source B", "url": "https://example.com/b", "text": "Another source excerpt."},
        ])
        self.assertIn("quantum computing", prompt)
        self.assertIn("[E1]", prompt)
        self.assertIn("[E2]", prompt)
        self.assertIn("disagree", prompt.lower())
        self.assertIn("Do not invent", prompt)


class ResearchCitationAuditTests(unittest.TestCase):
    def test_detects_valid_citation_labels_without_claiming_support(self):
        from backend.research_synthesis import audit_synthesis_citations
        notes = audit_synthesis_citations("Finding supported by [E1] and [E2].", 2)
        self.assertTrue(any("[E1], [E2]" in note for note in notes))
        self.assertTrue(any("does not prove" in note for note in notes))

    def test_warns_when_citations_are_missing(self):
        from backend.research_synthesis import audit_synthesis_citations
        notes = audit_synthesis_citations("A confident but uncited claim.", 2)
        self.assertTrue(any("No [E#]" in note for note in notes))

    def test_flags_unavailable_citation_ids(self):
        from backend.research_synthesis import audit_synthesis_citations
        notes = audit_synthesis_citations("Evidence [E1] and [E4].", 2)
        self.assertTrue(any("[E4]" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
