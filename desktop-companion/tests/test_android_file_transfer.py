import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import android_file_transfer as transfer


class TransferValidationTests(unittest.TestCase):
    def test_rejects_unapproved_remote_paths(self):
        for path in (
            "/sdcard/Android/data/com.example/private.db",
            "/sdcard/Download/../secret.txt",
            "/sdcard/Download/-unsafe.txt",
            "C:/Users/user/secret.txt",
        ):
            self.assertFalse(transfer._ALLOWED_PATH_RE.fullmatch(path) and "/../" not in path)

    def test_requires_confirmation(self):
        request = transfer.PullRequest(serial="usb-123", remote_path="/sdcard/Download/file.txt", confirmed=False)
        with patch.object(transfer, "_authorize"), patch.object(transfer, "_require_authorized_device") as device:
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as caught:
                transfer.pull_android_file(request, "test-token")
        self.assertEqual(caught.exception.status_code, 400)
        device.assert_not_called()

    def test_validates_path_before_adb(self):
        request = transfer.PullRequest(serial="usb-123", remote_path="/sdcard/Android/data/private.txt", confirmed=True)
        with patch.object(transfer, "_authorize"), patch.object(transfer, "_require_authorized_device") as device:
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as caught:
                transfer.pull_android_file(request, "test-token")
        self.assertEqual(caught.exception.status_code, 400)
        device.assert_not_called()


if __name__ == "__main__":
    unittest.main()
