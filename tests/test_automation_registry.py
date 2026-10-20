"""Unit tests for the truthful automation capability registry."""
import unittest

from backend.automation_registry import get_automation_capabilities


class AutomationRegistryTests(unittest.TestCase):
    def test_registry_is_versioned_and_nonempty(self):
        registry = get_automation_capabilities()
        self.assertEqual(registry["registry_version"], 1)
        self.assertTrue(registry["adapters"])

    def test_every_adapter_declares_status_actions_and_limits(self):
        for adapter in get_automation_capabilities()["adapters"]:
            with self.subTest(adapter=adapter["id"]):
                self.assertTrue(adapter["id"])
                self.assertTrue(adapter["status"])
                self.assertIsInstance(adapter["actions"], list)
                self.assertIsInstance(adapter["limitations"], list)

    def test_unimplemented_platforms_are_not_advertised_as_ready(self):
        registry = {item["id"]: item for item in get_automation_capabilities()["adapters"]}
        self.assertEqual(registry["ios_app_control"]["status"], "not_implemented")
        self.assertEqual(registry["general_browser_automation"]["status"], "not_implemented")
        self.assertEqual(registry["authenticated_service_connectors"]["status"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
