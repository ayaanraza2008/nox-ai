"""Tests for the approval-gated, session-scoped project workspace."""
import os
import tempfile
import unittest
from unittest.mock import patch

from backend import project_workspace as ws


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"NOX_WORKSPACE_DB": os.path.join(self.temp.name, "workspace.sqlite3")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _project_with_file(self, owner="owner-a"):
        project = ws.create_project("NOX demo", owner)
        saved = ws.save_file(project["id"], "src/main.py", "print('before')\n", owner)
        self.assertEqual(saved["version"], 1)
        return project

    def test_patch_is_preview_only_until_explicit_approval(self):
        project = self._project_with_file()
        patch = ws.create_patch(project["id"], "src/main.py", "print('after')\n", "Update greeting", "owner-a")
        self.assertEqual(patch["status"], "pending")
        self.assertEqual(ws.read_file(project["id"], "src/main.py", "owner-a")["content"], "print('before')\n")

        reviewed = ws.review_patch(patch["id"], "approved", "owner-a")
        self.assertEqual(reviewed["status"], "approved")
        saved = ws.read_file(project["id"], "src/main.py", "owner-a")
        self.assertEqual(saved["content"], "print('after')\n")
        self.assertEqual(saved["version"], 2)

    def test_patch_cannot_be_approved_if_original_changed(self):
        project = self._project_with_file()
        patch = ws.create_patch(project["id"], "src/main.py", "print('proposed')\n", "Try change", "owner-a")
        ws.save_file(project["id"], "src/main.py", "print('manual edit')\n", "owner-a")
        with self.assertRaisesRegex(ws.WorkspaceError, "stale"):
            ws.review_patch(patch["id"], "approved", "owner-a")
        self.assertEqual(ws.read_file(project["id"], "src/main.py", "owner-a")["content"], "print('manual edit')\n")

    def test_project_and_patch_data_are_scoped_to_owner(self):
        project = self._project_with_file()
        patch = ws.create_patch(project["id"], "src/main.py", "print('x')\n", "Try change", "owner-a")
        self.assertIsNone(ws.get_project(project["id"], "owner-b"))
        self.assertIsNone(ws.list_files(project["id"], "owner-b"))
        self.assertIsNone(ws.review_patch(patch["id"], "approved", "owner-b"))
        self.assertEqual(ws.read_file(project["id"], "src/main.py", "owner-a")["content"], "print('before')\n")

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        for path in ("../secret.txt", "/etc/passwd", "src/../secret.py", r"src\\secret.py", ".env"):
            with self.subTest(path=path), self.assertRaises(ws.WorkspaceError):
                ws.validate_path(path)

    def test_file_validation_parses_without_execution(self):
        project = self._project_with_file()
        valid = ws.validate_file(project["id"], "src/main.py", "owner-a")
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["validator"], "python AST")
        ws.save_file(project["id"], "config.json", '{"ok": true}', "owner-a")
        self.assertTrue(ws.validate_file(project["id"], "config.json", "owner-a")["valid"])

    def test_rejected_patch_does_not_change_file(self):
        project = self._project_with_file()
        patch = ws.create_patch(project["id"], "src/main.py", "print('after')\n", "Update greeting", "owner-a")
        reviewed = ws.review_patch(patch["id"], "rejected", "owner-a")
        self.assertEqual(reviewed["status"], "rejected")
        self.assertEqual(ws.read_file(project["id"], "src/main.py", "owner-a")["content"], "print('before')\n")


if __name__ == "__main__":
    unittest.main()
