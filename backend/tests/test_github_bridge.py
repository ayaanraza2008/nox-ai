"""Unit tests for GitHub bridge path, size, and change validation."""
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from backend import github_bridge as bridge


class GitHubBridgeValidationTests(unittest.TestCase):
    def test_safe_relative_paths(self):
        self.assertEqual(bridge._safe_path("src/main.py"), "src/main.py")
        for path in ("", "../secret", "/etc/passwd", "src/../x.py", r"src\\x.py",
                     ".env", "config/.secret", "keys/private.pem", "src/credentials"):
            with self.subTest(path=path), self.assertRaises(HTTPException):
                bridge._safe_path(path)

    def test_change_list_rejects_duplicate_paths(self):
        items = [
            SimpleNamespace(path="src/a.py", content="a", expected_sha="sha-a"),
            SimpleNamespace(path="src/a.py", content="b", expected_sha="sha-a"),
        ]
        with self.assertRaises(HTTPException) as caught:
            bridge._validate_changes(items)
        self.assertEqual(caught.exception.status_code, 400)

    def test_change_list_enforces_combined_size(self):
        items = [
            SimpleNamespace(path=f"src/file{i}.txt", content="x" * 50000, expected_sha=None)
            for i in range(4)
        ]
        with self.assertRaises(HTTPException) as caught:
            bridge._validate_changes(items)
        self.assertEqual(caught.exception.status_code, 413)

    def test_session_owner_requires_server_cookie(self):
        request = SimpleNamespace(cookies={})
        with self.assertRaises(HTTPException) as caught:
            bridge._owner(request)
        self.assertEqual(caught.exception.status_code, 401)
        valid = "a" * 48
        self.assertEqual(bridge._owner(SimpleNamespace(cookies={"nox_session": valid})), valid)

    def test_ci_endpoints_are_registered(self):
        paths = {route.path for route in bridge.router.routes}
        self.assertIn("/api/github/ci/runs", paths)
        self.assertIn("/api/github/ci/runs/{run_id}", paths)

    def test_repository_and_token_are_not_required_to_import_module(self):
        # Configuration is checked at request time, so NOX can boot without GitHub secrets.
        self.assertTrue(hasattr(bridge, "router"))


if __name__ == "__main__":
    unittest.main()
