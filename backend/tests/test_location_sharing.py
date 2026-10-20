"""Tests for consent gates, location freshness, and abuse guards."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException

from backend import location_sharing as location


class _Result:
    def __init__(self, row=None, rowcount=1):
        self.row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self.row


class _FakeConnection:
    def __init__(self, device):
        self.device = device

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        if "SELECT * FROM nox_location_devices WHERE token_hash" in query:
            return _Result(self.device)
        return _Result()


class LocationSharingTests(unittest.TestCase):
    def test_stale_location_is_not_online_or_current(self):
        now = datetime.now(timezone.utc)
        item = {
            "sharing_enabled": True,
            "consent_expires_at": now + timedelta(hours=1),
            "last_seen_at": now - timedelta(minutes=4),
            "last_location_at": now - timedelta(minutes=4),
            "latitude": 28.6,
            "longitude": 77.2,
            "accuracy_m": 25,
            "is_owner": False,
        }
        result = location.status_fields(item, now)
        self.assertFalse(result["online"])
        self.assertTrue(result["location_stale"])
        # Keep the last-known point available as stale data; the dashboard must not
        # draw it as a live marker because location_stale is true.
        self.assertEqual(result["latitude"], 28.6)
        self.assertEqual(result["longitude"], 77.2)

    def test_fresh_shared_location_requires_unexpired_consent(self):
        now = datetime.now(timezone.utc)
        item = {
            "sharing_enabled": True,
            "consent_expires_at": now + timedelta(minutes=30),
            "last_seen_at": now - timedelta(seconds=20),
            "last_location_at": now - timedelta(seconds=20),
            "latitude": 28.6,
            "longitude": 77.2,
            "accuracy_m": 12,
            "is_owner": False,
        }
        result = location.status_fields(item, now)
        self.assertTrue(result["online"])
        self.assertFalse(result["location_stale"])
        self.assertTrue(result["sharing_active"])
        self.assertEqual(result["latitude"], 28.6)

    def test_revoked_or_paused_consent_rejects_mobile_upload(self):
        device = {
            "id": "device-1",
            "owner_id": "owner-1",
            "sharing_enabled": False,
            "consent_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "last_location_at": None,
        }
        with patch.object(location, "_connect", return_value=_FakeConnection(device)):
            with self.assertRaises(HTTPException) as caught:
                location.update_location("valid-device-token", 28.6, 77.2, 10)
        self.assertEqual(caught.exception.status_code, 403)

    def test_expired_consent_rejects_mobile_upload(self):
        device = {
            "id": "device-1",
            "owner_id": "owner-1",
            "sharing_enabled": True,
            "consent_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
            "last_location_at": None,
        }
        with patch.object(location, "_connect", return_value=_FakeConnection(device)):
            with self.assertRaises(HTTPException) as caught:
                location.update_location("valid-device-token", 28.6, 77.2, 10)
        self.assertEqual(caught.exception.status_code, 403)

    def test_invalid_coordinates_rejected_before_database_access(self):
        with patch.object(location, "_connect", side_effect=AssertionError("database must not be reached")):
            with self.assertRaises(HTTPException) as caught:
                location.update_location("token", 100, 0, 10)
        self.assertEqual(caught.exception.status_code, 422)

    def test_location_token_required(self):
        with patch.object(location, "_connect", side_effect=AssertionError("database must not be reached")):
            with self.assertRaises(HTTPException) as caught:
                location.update_location("", 0, 0, 10)
        self.assertEqual(caught.exception.status_code, 401)

    def test_dashboard_requires_authenticated_nox_account(self):
        from starlette.requests import Request
        from backend import main
        request = Request({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "https", "path": "/api/location/devices",
            "raw_path": b"/api/location/devices", "query_string": b"",
            "headers": [], "client": ("testclient", 1234), "server": ("test", 443),
        })
        with self.assertRaises(HTTPException) as caught:
            main._location_account_owner(request)
        self.assertEqual(caught.exception.status_code, 401)

    def test_rate_limit_blocks_excess_requests(self):
        key = "test-location-rate-limit"
        location._RATE_BUCKETS.pop(key, None)
        location.rate_limit(key, limit=1, window_seconds=60)
        with self.assertRaises(HTTPException) as caught:
            location.rate_limit(key, limit=1, window_seconds=60)
        self.assertEqual(caught.exception.status_code, 429)
        location._RATE_BUCKETS.pop(key, None)

    def test_map_config_requires_https_style_url(self):
        with patch.dict(os.environ, {"NOX_MAP_STYLE_URL": "http://tiles.example/style.json"}):
            result = location.map_config()
        self.assertFalse(result["configured"])
        self.assertIsNone(result["map_style_url"])

    def test_map_config_accepts_https_style_url(self):
        with patch.dict(os.environ, {"NOX_MAP_STYLE_URL": "https://tiles.example/style.json"}):
            result = location.map_config()
        self.assertTrue(result["configured"])
        self.assertEqual(result["map_style_url"], "https://tiles.example/style.json")


if __name__ == "__main__":
    unittest.main()
