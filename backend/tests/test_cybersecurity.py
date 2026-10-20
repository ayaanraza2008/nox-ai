import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.cybersecurity import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

class CybersecurityApiTests(unittest.TestCase):
    def test_status_does_not_claim_local_device_access(self):
        data = client.get("/api/cybersecurity/status").json()
        self.assertFalse(data["local_device_access"])
        self.assertFalse(data["active_scanning_available_here"])
        self.assertTrue(all(item["version"] is None for item in data["tools"]))

    def test_code_review_detects_shell_true_and_redacts_secret(self):
        source = 'subprocess.run(cmd, shell=True)\nAPI_KEY = "supersecretvalue123"'
        response = client.post("/api/cybersecurity/code-review", json={"source": source})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["finding_count"], 2)
        self.assertTrue(any(item["rule"] == "shell-true" for item in data["findings"]))
        secret = next(item for item in data["findings"] if item["rule"] == "hardcoded-secret")
        self.assertNotIn("supersecretvalue123", secret["evidence"])

    def test_code_review_rejects_too_many_lines(self):
        source = "\n".join(["x = 1"] * 2001)
        response = client.post("/api/cybersecurity/code-review", json={"source": source})
        self.assertEqual(response.status_code, 413)

    def test_command_explainer_does_not_accept_shell_chaining(self):
        self.assertEqual(client.post("/api/cybersecurity/explain-command", json={"command": "ss -lnt"}).status_code, 200)
        self.assertEqual(client.post("/api/cybersecurity/explain-command", json={"command": "ss -lnt; whoami"}).status_code, 400)

    def test_scope_requires_authorization_and_lab_or_allowlist(self):
        body = {"target": "127.0.0.1", "scope_note": "local development lab", "authorized": False}
        self.assertEqual(client.post("/api/cybersecurity/validate-scope", json=body).status_code, 403)
        body["authorized"] = True
        self.assertEqual(client.post("/api/cybersecurity/validate-scope", json=body).status_code, 200)
        body["target"] = "example.com"
        self.assertEqual(client.post("/api/cybersecurity/validate-scope", json=body).status_code, 403)

if __name__ == "__main__":
    unittest.main()
