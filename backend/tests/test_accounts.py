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

    def test_logout_other_sessions_requires_token_without_database(self):
        with self.assertRaisesRegex(ValueError, "sign in again"):
            accounts.logout_other_sessions("")

    def test_logout_other_sessions_revokes_others_but_preserves_current(self):
        class Cursor:
            def __init__(self, row=None, rowcount=0):
                self.row = row
                self.rowcount = rowcount
            def fetchone(self):
                return self.row

        class FakeConnection:
            def __init__(self):
                self.committed = False
                self.closed = False
                self.calls = []
            def execute(self, query, params=()):
                self.calls.append((query, params))
                if "SELECT s.account_id" in query:
                    return Cursor({"account_id": "account-1"})
                if "UPDATE nox_account_sessions SET revoked=1" in query:
                    return Cursor(rowcount=2)
                raise AssertionError("Unexpected SQL: " + query)
            def commit(self):
                self.committed = True
            def rollback(self):
                pass
            def close(self):
                self.closed = True

        connection = FakeConnection()
        with patch.object(accounts, "_connect", return_value=connection):
            revoked = accounts.logout_other_sessions("current-token")
        self.assertEqual(revoked, 2)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        update_sql, update_params = connection.calls[1]
        self.assertIn("token_hash<>%s", update_sql)
        self.assertEqual(update_params[0], "account-1")
        self.assertNotEqual(update_params[1], "current-token")


if __name__ == "__main__":
    unittest.main()
