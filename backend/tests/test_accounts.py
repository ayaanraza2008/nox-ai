"""Regression tests for NOX account verification, authentication, and recovery."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend import accounts


class Cursor:
    def __init__(self, row=None, rowcount=1):
        self.row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, account=None, challenge=None, duplicate=None, expired=False):
        self.account = account
        self.challenge = challenge
        self.duplicate = duplicate
        self.expired = expired
        self.calls = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, query, params=()):
        self.calls.append((query, params))
        if "SELECT window_start,count FROM nox_account_rate_limits" in query:
            return Cursor(None)
        if "SELECT id FROM nox_accounts WHERE email=%s OR username=%s" in query:
            return Cursor(self.duplicate)
        if "SELECT a.* FROM nox_account_sessions s JOIN nox_accounts a" in query:
            return Cursor(self.account)
        if "SELECT * FROM nox_account_challenges" in query:
            return Cursor(self.challenge)
        if "UPDATE nox_accounts SET email_verified=TRUE" in query and self.account:
            self.account["email_verified"] = True
        if "UPDATE nox_accounts SET phone_verified=TRUE" in query and self.account:
            self.account["phone_verified"] = True
        if "UPDATE nox_accounts SET status=CASE" in query and self.account:
            self.account["status"] = "active" if self.account.get("email_verified") and self.account.get("phone_verified") else ("email_verified" if self.account.get("email_verified") else ("phone_verified" if self.account.get("phone_verified") else "pending_verification"))
        if "SELECT * FROM nox_accounts WHERE email=%s" in query:
            return Cursor(self.account)
        if "SELECT * FROM nox_accounts WHERE username=%s" in query:
            return Cursor(self.account)
        if "SELECT * FROM nox_accounts WHERE country_code=%s AND phone_number=%s" in query:
            return Cursor(self.account)
        if "SELECT * FROM nox_accounts WHERE id=%s" in query:
            return Cursor(self.account)
        if "SELECT s.account_id FROM nox_account_sessions" in query:
            return Cursor({"account_id": (self.account or {}).get("id", "account-1")})
        return Cursor(None, rowcount=1)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def account_row(**overrides):
    row = {
        "id": "account-1",
        "email": "person@example.com",
        "full_name": "Example Person",
        "username": "example_person",
        "country_code": "+91",
        "phone_number": "9876543210",
        "password_salt": "",
        "password_hash": accounts._PASSWORDS.hash("correct horse battery staple"),
        "password_scheme": "argon2id",
        "email_verified": False,
        "phone_verified": False,
        "status": "pending_verification",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    row.update(overrides)
    return row


class AccountSecurityTests(unittest.TestCase):
    def test_argon2id_password_hash_verifies_only_matching_password(self):
        hashed = accounts._PASSWORDS.hash("correct horse battery staple")
        self.assertTrue(hashed.startswith("$argon2id$"))
        row = account_row(password_hash=hashed, password_scheme="argon2id")
        self.assertTrue(accounts._password_matches(row, "correct horse battery staple"))
        self.assertFalse(accounts._password_matches(row, "wrong password"))

    def test_legacy_pbkdf2_hash_still_verifies_for_migration(self):
        salt = b"0123456789abcdef"
        encoded = accounts._hash_password("correct horse battery staple", salt)
        self.assertTrue(accounts._verify_password("correct horse battery staple", salt.hex(), encoded))
        self.assertFalse(accounts._verify_password("wrong password", salt.hex(), encoded))

    def test_registration_rejects_invalid_email_before_database_access(self):
        with self.assertRaisesRegex(ValueError, "valid email"):
            accounts.register("Example Person", "example_person", "not-an-email", "+91", "9876543210",
                              "a sufficiently long password")

    def test_registration_rejects_short_password_before_database_access(self):
        with self.assertRaisesRegex(ValueError, "10"):
            accounts.register("Example Person", "example_person", "person@example.com", "+91", "9876543210", "short")

    def test_profile_normalizes_username_and_requires_exactly_ten_digits(self):
        profile = accounts._validate_profile("  Example   Person ", "Example_Person", "+91", "9876543210")
        self.assertEqual(profile, ("Example Person", "example_person", "+91", "9876543210"))
        with self.assertRaisesRegex(ValueError, "exactly 10"):
            accounts._validate_profile("Example Person", "example_person", "+91", "12345")

    def test_duplicate_registration_is_rejected(self):
        connection = FakeConnection(duplicate={"id": "existing"})
        with patch.object(accounts, "_connect", return_value=connection):
            with self.assertRaisesRegex(ValueError, "already exists"):
                accounts.register("Example Person", "example_person", "person@example.com", "+91",
                                  "9876543210", "a sufficiently long password", "127.0.0.1")
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_login_supports_username_email_and_mobile(self):
        for identifier, expected_fragment in (
            ("example_person", "WHERE username=%s"),
            ("PERSON@example.com", "WHERE email=%s"),
            ("9876543210", "WHERE country_code=%s AND phone_number=%s"),
        ):
            with self.subTest(identifier=identifier):
                row = account_row()
                connection = FakeConnection(account=row)
                with patch.object(accounts, "_connect", return_value=connection):
                    result = accounts.login(identifier, "correct horse battery staple", "+91", "127.0.0.1")
                self.assertEqual(result["account"]["id"], "account-1")
                self.assertTrue(any(expected_fragment in query for query, _ in connection.calls))
                self.assertTrue(connection.committed)

    def test_wrong_password_does_not_create_session(self):
        connection = FakeConnection(account=account_row())
        with patch.object(accounts, "_connect", return_value=connection):
            with self.assertRaisesRegex(ValueError, "incorrect"):
                accounts.login("example_person", "wrong password", "+91", "127.0.0.1")
        self.assertFalse(any("INSERT INTO nox_account_sessions" in query for query, _ in connection.calls))

    def test_expired_verification_code_is_rejected(self):
        row = account_row()
        challenge = {
            "id": "challenge-1", "account_id": "account-1", "purpose": "email_verify",
            "code_hash": "unused", "attempts": 0,
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        }
        connection = FakeConnection(account=row, challenge=challenge)
        with patch.object(accounts, "_connect", return_value=connection):
            with self.assertRaisesRegex(ValueError, "expired"):
                accounts.verify_code("session-token", "email_verify", "email", "123456")
        self.assertTrue(connection.committed)

    def test_successful_email_verification_updates_status_only_after_valid_code(self):
        row = account_row()
        challenge = {
            "id": "challenge-1", "account_id": "account-1", "purpose": "email_verify",
            "code_hash": "unused", "attempts": 0,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
        connection = FakeConnection(account=row, challenge=challenge)
        with patch.object(accounts, "_connect", return_value=connection), \
             patch.object(accounts, "_verification_secret", return_value="test-secret"), \
             patch.object(accounts, "_code_hash", side_effect=lambda code: "expected-hash" if code == "123456" else "wrong"):
            challenge["code_hash"] = "expected-hash"
            result = accounts.verify_code("session-token", "email_verify", "email", "123456")
        self.assertTrue(result["email_verified"])
        self.assertEqual(result["status"], "email_verified")
        self.assertTrue(any("email_verified=TRUE" in query for query, _ in connection.calls))
        self.assertTrue(any("consumed_at=%s" in query for query, _ in connection.calls))

    def test_recovery_response_does_not_reveal_account_existence(self):
        no_account_conn = FakeConnection()
        existing_conn = FakeConnection(account=account_row())
        with patch.object(accounts, "_connect", side_effect=[no_account_conn, existing_conn]), \
             patch.object(accounts, "_send_challenge", return_value="setup_required"):
            missing = accounts.request_recovery("missing@example.com", "email", "+91", "127.0.0.1")
            existing = accounts.request_recovery("person@example.com", "email", "+91", "127.0.0.1")
        self.assertEqual(missing, existing)
        self.assertIn("If a matching account exists", missing)

    def test_successful_mobile_verification_updates_phone_flag(self):
        row = account_row()
        challenge = {
            "id": "challenge-phone", "account_id": "account-1", "purpose": "phone_verify",
            "code_hash": "expected-hash", "attempts": 0,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
        connection = FakeConnection(account=row, challenge=challenge)
        with patch.object(accounts, "_connect", return_value=connection), \
             patch.object(accounts, "_code_hash", side_effect=lambda code: "expected-hash" if code == "654321" else "wrong"):
            result = accounts.verify_code("session-token", "phone_verify", "sms", "654321")
        self.assertTrue(result["phone_verified"])
        self.assertEqual(result["status"], "phone_verified")
        self.assertTrue(any("phone_verified=TRUE" in query for query, _ in connection.calls))

    def test_password_recovery_reset_hashes_new_password_and_revokes_sessions(self):
        row = account_row()
        challenge = {
            "id": "challenge-reset", "account_id": "account-1", "purpose": "password_reset_email",
            "code_hash": "expected-hash", "attempts": 0,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
        connection = FakeConnection(account=row, challenge=challenge)
        with patch.object(accounts, "_connect", return_value=connection), \
             patch.object(accounts, "_code_hash", return_value="expected-hash"):
            result = accounts.reset_password("person@example.com", "email", "+91", "123456",
                                             "a new sufficiently long password", "127.0.0.1")
        self.assertTrue(result)
        self.assertTrue(any("password_scheme='argon2id'" in query for query, _ in connection.calls))
        self.assertTrue(any("UPDATE nox_account_sessions SET revoked=1" in query for query, _ in connection.calls))
        self.assertTrue(connection.committed)

    def test_logout_revokes_session_without_deleting_account(self):
        connection = FakeConnection(account=account_row())
        with patch.object(accounts, "_connect", return_value=connection):
            accounts.logout("session-token")
        self.assertTrue(any("UPDATE nox_account_sessions SET revoked=1" in query for query, _ in connection.calls))
        self.assertFalse(any("DELETE FROM nox_accounts" in query for query, _ in connection.calls))
        self.assertTrue(connection.committed)

    def test_remember_me_session_duration_is_bounded(self):
        connection = FakeConnection()
        with patch.object(accounts, "_now", return_value=datetime(2026, 1, 1, tzinfo=timezone.utc)):
            token, max_age = accounts._new_session(connection, "account-1", remember_me=False)
        self.assertTrue(token)
        self.assertEqual(max_age, 86400)

    def test_empty_account_session_does_not_connect_to_database(self):
        self.assertIsNone(accounts.resolve_session(""))

    def test_logout_other_sessions_requires_token_without_database(self):
        with self.assertRaisesRegex(ValueError, "sign in again"):
            accounts.logout_other_sessions("")

    def test_logout_other_sessions_preserves_current_session(self):
        connection = FakeConnection(account=account_row())
        with patch.object(accounts, "_connect", return_value=connection):
            revoked = accounts.logout_other_sessions("current-token")
        self.assertEqual(revoked, 1)
        update_sql = next(query for query, _ in connection.calls if "UPDATE nox_account_sessions SET revoked=1" in query)
        self.assertIn("token_hash<>%s", update_sql)


if __name__ == "__main__":
    unittest.main()
