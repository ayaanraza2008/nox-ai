"""Unit tests for the truthful automation capability registry."""
import unittest

from backend.automation_registry import get_automation_capabilities


class AutomationRegistryTests(unittest.TestCase):
    def test_registry_is_versioned_and_nonempty(self):
        registry = get_automation_capabilities()
        self.assertEqual(registry["registry_version"], 2)
        self.assertTrue(registry["adapters"])

    def test_every_adapter_declares_status_actions_and_limits(self):
        for adapter in get_automation_capabilities()["adapters"]:
            with self.subTest(adapter=adapter["id"]):
                self.assertTrue(adapter["id"])
                self.assertTrue(adapter["status"])
                self.assertIsInstance(adapter["actions"], list)
                self.assertIsInstance(adapter["limitations"], list)

    def test_runtime_flags_are_explicit_and_never_claim_local_companion_is_online(self):
        registry = get_automation_capabilities(ai_configured=True, browser_available=False)
        self.assertTrue(registry["runtime"]["ai_provider_configured"])
        self.assertFalse(registry["runtime"]["playwright_package_available"])
        self.assertFalse(registry["runtime"]["server_can_detect_local_companion_online"])
        adapters = {item["id"]: item for item in registry["adapters"]}
        self.assertEqual(adapters["remote_browser_automation"]["status"], "setup_required")
        self.assertEqual(adapters["public_web_research"]["status"], "ready")

    def test_unimplemented_platforms_are_not_advertised_as_ready(self):
        registry = {item["id"]: item for item in get_automation_capabilities()["adapters"]}
        self.assertEqual(registry["ios_app_control"]["status"], "not_implemented")
        self.assertEqual(registry["remote_browser_automation"]["status"], "implemented_with_setup")
        self.assertIn("verify_visible_page_change", registry["remote_browser_automation"]["actions"])
        self.assertIn("research_public_sources_to_markdown_report", registry["remote_browser_automation"]["actions"])
        self.assertEqual(registry["authenticated_service_connectors"]["status"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
