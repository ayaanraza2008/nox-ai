"""Tests for bounded public-web fetch behavior."""
import unittest
from unittest.mock import patch

import httpx

from backend import autonomous_agent as agent


class PublicPageDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def _fetch_with_response(self, response):
        transport = httpx.MockTransport(lambda request: response)
        client_class = httpx.AsyncClient

        def make_client(*args, **kwargs):
            kwargs["transport"] = transport
            return client_class(*args, **kwargs)

        with patch.object(agent, "_public_http_url", side_effect=lambda value: value), \
             patch.object(agent.httpx, "AsyncClient", side_effect=make_client):
            return await agent._get_public("https://example.com/page")

    async def test_small_public_text_page_is_read(self):
        response = httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=b"public facts",
            request=httpx.Request("GET", "https://example.com/page"),
        )
        url, content_type, body = await self._fetch_with_response(response)
        self.assertEqual(url, "https://example.com/page")
        self.assertIn("text/plain", content_type)
        self.assertEqual(body, "public facts")

    async def test_oversized_page_is_rejected(self):
        response = httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "500001"},
            content=b"x",
            request=httpx.Request("GET", "https://example.com/page"),
        )
        with self.assertRaisesRegex(ValueError, "500 KB"):
            await self._fetch_with_response(response)

    async def test_non_text_content_is_rejected(self):
        response = httpx.Response(
            200,
            headers={"content-type": "application/octet-stream"},
            content=b"binary",
            request=httpx.Request("GET", "https://example.com/page"),
        )
        with self.assertRaisesRegex(ValueError, "HTML and plain-text"):
            await self._fetch_with_response(response)


if __name__ == "__main__":
    unittest.main()
