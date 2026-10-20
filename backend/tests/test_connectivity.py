"""Tests for evidence-based browser connectivity analysis."""
import unittest

import httpx
from backend import main
from backend.connectivity import analyze_browser_observations


class ConnectivityAnalysisTests(unittest.TestCase):
    def test_offline_flag_is_reported_as_observed_not_router_failure(self):
        result = analyze_browser_observations({"online": False, "sampled_at": "2026-10-20T10:00:00Z"})
        finding = next(item for item in result["findings"] if item["code"] == "browser_offline")
        self.assertEqual(finding["certainty"], "observed")
        self.assertIn("does not identify the router", finding["detail"])

    def test_online_flag_does_not_claim_internet_is_verified(self):
        result = analyze_browser_observations({"online": True})
        finding = next(item for item in result["findings"] if item["code"] == "browser_online_flag")
        self.assertIn("does not guarantee", finding["detail"])

    def test_low_connection_estimate_is_labeled_estimated(self):
        result = analyze_browser_observations({"online": True, "effective_type": "2g", "downlink_mbps": 0.5})
        findings = {item["code"]: item for item in result["findings"]}
        self.assertEqual(findings["slow_connection_estimate"]["certainty"], "estimated")
        self.assertEqual(findings["low_downlink_estimate"]["certainty"], "estimated")

    def test_unsupported_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "effective connection type"):
            analyze_browser_observations({"effective_type": "wifi-7"})
        with self.assertRaisesRegex(ValueError, "downlink_mbps"):
            analyze_browser_observations({"downlink_mbps": -1})
        with self.assertRaisesRegex(ValueError, "rtt_ms"):
            analyze_browser_observations({"rtt_ms": 900000})

    def test_report_discloses_browser_limitations_and_no_control(self):
        result = analyze_browser_observations({})
        self.assertEqual(result["source"], "browser_network_information_api")
        self.assertTrue(any("SSID" in item for item in result["limitations"]))
        self.assertEqual(result["findings"], [])


class ConnectivityEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_endpoint_requires_valid_browser_session(self):
        response = await self.client.post(
            "/api/connectivity/analyze",
            json={"observations": {"online": True}},
        )
        self.assertEqual(response.status_code, 401)

    async def test_endpoint_returns_bounded_evidence_report(self):
        self.client.cookies.set(main.SESSION_COOKIE, "a" * 40)
        response = await self.client.post(
            "/api/connectivity/analyze",
            json={"observations": {"online": True, "effective_type": "4g"}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["scope"], "user_requested_browser_observations")
        self.assertFalse(payload["control_available"])
        self.assertTrue(payload["findings"])

    async def test_endpoint_rejects_oversized_observation_payload(self):
        self.client.cookies.set(main.SESSION_COOKIE, "a" * 40)
        response = await self.client.post(
            "/api/connectivity/analyze",
            json={"observations": {"extra": "x" * 9000}},
        )
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
