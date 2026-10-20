import unittest

from backend.main import _stream_retry_provider


class StreamRetryProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = {
            "name": "OpenRouter",
            "model": "some-configured-model",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "key": "test-only",
            "headers": {},
        }

    def test_transient_error_gets_one_same_model_retry(self):
        retry = _stream_retry_provider(self.provider, status_code=503)
        self.assertEqual(retry["model"], "some-configured-model")
        self.assertTrue(retry["_stream_retried"])
        self.assertNotIn("_stream_fallback_model", retry)

    def test_exhausted_transient_retry_falls_back_to_free_router(self):
        retried = {**self.provider, "_stream_retried": True}
        fallback = _stream_retry_provider(retried, status_code=503)
        self.assertEqual(fallback["model"], "openrouter/free")
        self.assertTrue(fallback["_stream_fallback_model"])
        self.assertNotIn("_stream_retried", fallback)

    def test_rejected_model_falls_back_without_retrying_same_model(self):
        fallback = _stream_retry_provider(self.provider, status_code=404)
        self.assertEqual(fallback["model"], "openrouter/free")

    def test_auth_failure_does_not_retry_same_provider_or_model(self):
        self.assertIsNone(_stream_retry_provider(self.provider, status_code=401))
        self.assertIsNone(_stream_retry_provider(self.provider, status_code=403))

    def test_free_router_is_not_fallback_looped(self):
        free_provider = {**self.provider, "model": "openrouter/free", "_stream_retried": True}
        self.assertIsNone(_stream_retry_provider(free_provider, status_code=503))

    def test_connection_failure_gets_one_bounded_retry(self):
        retry = _stream_retry_provider(self.provider, connection_failure=True)
        self.assertTrue(retry["_stream_retried"])
        self.assertEqual(retry["model"], "some-configured-model")


if __name__ == "__main__":
    unittest.main()
