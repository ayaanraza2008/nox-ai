"""Unit tests for NOX account validation and password hashing."""
import unittest
from unittest.mock import patch

from backend import accounts


class AccountSecurityTests(unittest.TestCase):
    def test_password_hash_verifies_only_matching_password(self):
        salt = b"0123456789abcdef"
        encoded = accounts._hash_password("correct horse battery staple", salt)
        self.assertTrue(accounts._verify_password("correct horse battery staple", salt.hex(), encoded))
        self.assertFalse(accounts._verify_password("wrong password", salt.hex(), encoded))

    def test_registration_rejects_invalid_email_without_database(self):
        with self.assertRaisesRegex(ValueError, "valid email"):
            accounts.register("not-an-email", "a sufficiently long password")

    def test_registration_requires_long_password_without_database(self):
        with self.assertRaisesRegex(ValueError, "10"):
            accounts.register("person@example.com", "short")

    def test_empty_account_session_does_not_connect_to_database(self):
        self.assertIsNone(accounts.resolve_session(""))


if __name__ == "__main__":
    unittest.main()
