import asyncio
import base64
import unittest
from email import message_from_bytes
from unittest.mock import patch

from fastapi import HTTPException
from backend import communications


class CommunicationAdapterTests(unittest.TestCase):
    def test_provider_registry_does_not_claim_unimplemented_apps_connected(self):
        registry = communications.provider_registry()
        self.assertEqual(registry["gmail"]["actions"], ["search_mail", "save_draft", "send_email"])
        for provider in ("outlook", "whatsapp", "linkedin", "sms", "phone", "calendar"):
            self.assertEqual(registry[provider]["actions"], [])
            self.assertIsNone(registry[provider]["adapter"])

    def test_email_message_encodes_valid_rfc822_content(self):
        raw = communications._email_message(
            "rahul@example.com", "Project update", "I will send the update tomorrow.",
            cc="team@example.com"
        )
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        message = message_from_bytes(decoded)
        self.assertEqual(message["To"], "rahul@example.com")
        self.assertEqual(message["Cc"], "team@example.com")
        self.assertEqual(message["Subject"], "Project update")
        self.assertIn("send the update tomorrow", message.get_payload())

    def test_rejects_invalid_or_multiple_recipient_addresses(self):
        for address in ("not-an-email", "a@example.com,b@example.com", "a@localhost"):
            with self.subTest(address=address), self.assertRaises(HTTPException):
                communications._email_message(address, "Subject", "Body")

    def test_send_requires_explicit_confirmation_before_network_access(self):
        from starlette.requests import Request
        payload = communications.EmailSendRequest(to="rahul@example.com", subject="Update", body="Hello", confirmed=False)
        request = Request({"type":"http","method":"POST","scheme":"http","server":("127.0.0.1",8000),
                           "client":("127.0.0.1",1234),"path":"/api/connected/gmail/send",
                           "raw_path":b"/api/connected/gmail/send","query_string":b"",
                           "headers":[(b"cookie",b"nox_session=" + b"a"*40)]})
        with patch.object(communications, "_gmail_request", side_effect=AssertionError("network must not be called")):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(communications.gmail_send(payload, request))
        self.assertEqual(caught.exception.status_code, 428)

    def test_token_encryption_key_is_required(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(HTTPException) as caught:
                communications._fernet()
        self.assertEqual(caught.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
