"""Tests for privacy-conscious public research helpers."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from backend import public_research as research
from backend.main import app


class PublicResearchTests(unittest.IsolatedAsyncioTestCase):
    def test_public_research_endpoint_is_registered(self):
        paths = {route.path for route in app.routes if hasattr(route, "path")}
        self.assertIn("/api/research/public", paths)

    def test_email_syntax_validation(self):
        self.assertTrue(research.EMAIL_RE.fullmatch("support@example.com"))
        self.assertFalse(research.EMAIL_RE.fullmatch("not-an-email"))
        self.assertFalse(research.EMAIL_RE.fullmatch("name@localhost"))

    def test_phone_input_validation(self):
        self.assertTrue(research.PHONE_RE.fullmatch("+1 (415) 555-0100"))
        self.assertFalse(research.PHONE_RE.fullmatch("not a number"))

    def test_social_urls_are_limited_to_known_public_hosts(self):
        self.assertEqual(research._validate_social("https://www.instagram.com/public_name/")[1], "instagram.com")
        with self.assertRaises(ValueError):
            research._validate_social("https://example.com/profile")
        with self.assertRaises(ValueError):
            research._validate_social("http://instagram.com/public_name")
        with self.assertRaises(ValueError):
            research._validate_social("https://user:pass@instagram.com/public_name")

    def test_search_results_only_keep_http_links_and_bound_text(self):
        items = [
            {"title": "Public page", "url": "https://example.com/a", "snippet": "visible"},
            {"title": "Bad link", "url": "javascript:alert(1)", "snippet": "no"},
        ]
        out = research._search_results(json.dumps(items))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["url"], "https://example.com/a")

    async def test_invalid_email_does_not_search(self):
        with patch.object(research, "web_search", new_callable=AsyncMock) as search:
            result = await research.research_email("not-an-email")
        search.assert_not_awaited()
        self.assertFalse(result["syntax_valid"])
        self.assertTrue(result["warnings"])

    async def test_valid_email_returns_dns_and_source_evidence_separately(self):
        with patch.object(research, "_domain_metadata", new_callable=AsyncMock,
                          return_value={"domain": "example.com", "mx_records": ["10 mail.example.com"], "a_records": [], "source": "test"}), \
             patch.object(research, "web_search", new_callable=AsyncMock,
                          return_value=json.dumps([{"title": "Example public page", "url": "https://example.com/contact", "snippet": "Contact"}])):
            result = await research.research_email("support@example.com")
        self.assertIn("The domain publishes MX DNS records.", result["confirmed_facts"])
        self.assertEqual(result["sources"][0]["url"], "https://example.com/contact")
        self.assertTrue(any("do not prove a mailbox exists" in x for x in result["limits"]))

    async def test_social_search_is_public_query_only(self):
        with patch.object(research, "web_search", new_callable=AsyncMock,
                          return_value=json.dumps([{"title": "Public profile result", "url": "https://instagram.com/public_name", "snippet": "Public result"}])) as search:
            result = await research.research_social("https://www.instagram.com/public_name/")
        search.assert_awaited_once()
        self.assertEqual(result["sources"][0]["title"], "Public profile result")
        self.assertTrue(any("Private profiles" in x for x in result["limits"]))


if __name__ == "__main__":
    unittest.main()
