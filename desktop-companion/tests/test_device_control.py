import subprocess
import unittest

from device_control import discover_adb_devices, launch_android_app


class FakeResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class DeviceControlTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def runner(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[1:] == ["devices", "-l"]:
            return FakeResult(
                "List of devices attached\n"
                "usb-123 device product:pixel model:Pixel_8 device:husky\n"
                "usb-locked unauthorized usb:1-2\n"
                "usb-offline offline\n"
            )
        if "monkey" in args:
            return FakeResult("Events injected: 1")
        return FakeResult("")

    def test_discovery_marks_authorization_and_capabilities(self):
        result = discover_adb_devices(adb_path="adb-test", runner=self.runner)
        self.assertEqual(result["count"], 3)
        self.assertTrue(result["devices"][0]["authorized"])
        self.assertEqual(result["devices"][0]["name"], "Pixel 8")
        self.assertFalse(result["devices"][1]["capabilities"]["app_launch"])
        self.assertFalse(result["capabilities"]["bluetooth_discovery"])

    def test_missing_confirmation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "confirmation"):
            launch_android_app("usb-123", "com.example.app", False, "adb-test", self.runner)

    def test_invalid_package_is_rejected_before_process_execution(self):
        with self.assertRaisesRegex(ValueError, "package name"):
            launch_android_app("usb-123", "com.example;whoami", True, "adb-test", self.runner)
        self.assertEqual(self.calls, [])

    def test_unauthorized_device_is_not_controlled(self):
        with self.assertRaisesRegex(PermissionError, "unauthorized"):
            launch_android_app("usb-locked", "com.example.app", True, "adb-test", self.runner)

    def test_launch_uses_fixed_argv_and_is_not_claimed_verified(self):
        result = launch_android_app("usb-123", "com.example.app", True, "adb-test", self.runner)
        self.assertEqual(result["status"], "launch_requested_not_verified")
        self.assertFalse(result["verified"])
        args, kwargs = self.calls[-1]
        self.assertIn("monkey", args)
        self.assertIs(kwargs["shell"], False)

    def test_offline_device_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            launch_android_app("usb-offline", "com.example.app", True, "adb-test", self.runner)


if __name__ == "__main__":
    unittest.main()
