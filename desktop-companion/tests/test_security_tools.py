"""Regression tests for NOX's defensive security helpers; network calls are mocked."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve()
COMPANION_DIR = HERE.parents[1]
sys.path.insert(0, str(COMPANION_DIR))

import security_audit
import dependency_audit
import ethical_hacking
import companion


class StaticAuditTests(unittest.TestCase):
    def test_detects_common_patterns_and_skips_generated_dirs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.py").write_text(
                "import subprocess\nvalue = eval(user_input)\nsubprocess.run(cmd, shell=True)\n",
                encoding="utf-8",
            )
            generated = root / "node_modules"
            generated.mkdir()
            (generated / "ignored.py").write_text("eval(x)\n", encoding="utf-8")
            with patch.dict(os.environ, {"NOX_SECURITY_PROJECT_DIR": temp}):
                result = security_audit.audit_project()
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["files_scanned"], 1)
            self.assertGreaterEqual(result["finding_count"], 2)
            self.assertTrue(all(item["file"] == "app.py" for item in result["findings"]))

    def test_missing_project_setting_is_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            result = security_audit.audit_project()
        self.assertEqual(result["status"], "error")
        self.assertIn("NOX_SECURITY_PROJECT_DIR", result["message"])


class DependencyAuditTests(unittest.TestCase):
    def test_parses_pinned_python_and_npm_lock_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "requirements.txt").write_text(
                "requests==2.31.0\nflask>=3.0\n# comment\n", encoding="utf-8"
            )
            (root / "package-lock.json").write_text(json.dumps({
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "sample", "version": "1.0.0"},
                    "node_modules/lodash": {"version": "4.17.20"},
                    "node_modules/@scope/pkg": {"version": "1.2.3"},
                },
            }), encoding="utf-8")
            deps, skipped, total = dependency_audit._read_dependencies(root)
            names = {(item["name"], item["version"], item["ecosystem"]) for item in deps}
            self.assertIn(("requests", "2.31.0", "PyPI"), names)
            self.assertIn(("lodash", "4.17.20", "npm"), names)
            self.assertIn(("@scope/pkg", "1.2.3", "npm"), names)
            self.assertEqual(total, 3)
            self.assertEqual(skipped, [])

    def test_advisory_matches_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "requirements.txt").write_text("demo-package==1.0.0\n", encoding="utf-8")
            with patch.dict(os.environ, {"NOX_SECURITY_PROJECT_DIR": temp}), patch.object(
                dependency_audit, "_query_osv",
                return_value=[{"id": "OSV-TEST", "summary": "Test advisory", "references": []}],
            ):
                result = dependency_audit.audit_dependencies()
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["dependencies_checked"], 1)
            self.assertEqual(result["advisory_matches"], 1)
            self.assertEqual(result["findings"][0]["advisory"]["id"], "OSV-TEST")

    def test_report_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"NOX_SECURITY_PROJECT_DIR": temp}):
                result = dependency_audit.write_report(
                    {"status": "success", "files_scanned": 1, "finding_count": 0, "findings": []},
                    {"status": "success", "dependencies_checked": 1, "advisory_matches": 0, "findings": []},
                )
            self.assertEqual(result["status"], "success")
            self.assertTrue(Path(result["json_report"]).is_file())
            self.assertTrue(Path(result["markdown_report"]).is_file())
            report = json.loads(Path(result["json_report"]).read_text(encoding="utf-8"))
            self.assertEqual(report["project"], Path(temp).name)


class CompanionSecurityCommandTests(unittest.TestCase):
    def test_static_audit_command_is_dispatched(self):
        expected = {"status": "success", "finding_count": 0}
        with patch.object(companion, "audit_project", return_value=expected) as audit:
            result = companion.handle_security_command("AUDIT PROJECT SECURITY")
        self.assertEqual(result, expected)
        audit.assert_called_once_with()

    def test_dependency_aliases_are_dispatched(self):
        expected = {"status": "success", "dependencies_checked": 2}
        with patch.object(companion, "audit_dependencies", return_value=expected) as audit:
            result = companion.handle_security_command("check dependency vulnerabilities")
        self.assertEqual(result, expected)
        audit.assert_called_once_with()

    def test_report_command_runs_both_audits_and_writer(self):
        static_result = {"status": "success", "finding_count": 1}
        dependency_result = {"status": "success", "dependencies_checked": 2}
        report_result = {"status": "success", "json_report": "/tmp/security-report.json"}
        with patch.object(companion, "audit_project", return_value=static_result) as static_audit, \
             patch.object(companion, "audit_dependencies", return_value=dependency_result) as dependency_audit, \
             patch.object(companion, "write_report", return_value=report_result) as writer:
            result = companion.handle_security_command("generate security report")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["static_analysis"], static_result)
        self.assertEqual(result["dependency_audit"], dependency_result)
        self.assertEqual(result["report_files"], report_result)
        static_audit.assert_called_once_with()
        dependency_audit.assert_called_once_with()
        writer.assert_called_once_with(static_result, dependency_result)

    def test_website_command_only_accepts_supported_https_phrase(self):
        expected = {"status": "success", "summary": "headers checked"}
        with patch.object(companion, "check_website_security", return_value=expected) as checker:
            result = companion.handle_security_command("security check https://example.com")
            self.assertEqual(result, expected)
            checker.assert_called_once_with("https://example.com")
            self.assertIsNone(companion.handle_security_command("security check http://example.com"))
            self.assertIsNone(companion.handle_security_command("run exploit https://example.com"))

    def test_unrelated_commands_are_not_consumed(self):
        self.assertIsNone(companion.handle_security_command("open youtube"))


class WebsiteCheckSafetyTests(unittest.TestCase):
    def test_rejects_non_https_and_nonstandard_port_before_network(self):
        with patch.object(ethical_hacking.socket, "getaddrinfo") as dns:
            result = ethical_hacking.check_website_security("http://example.com")
            self.assertEqual(result["status"], "error")
            dns.assert_not_called()
            result = ethical_hacking.check_website_security("https://example.com:8443")
            self.assertEqual(result["status"], "error")
            dns.assert_not_called()

    def test_blocks_private_dns_results(self):
        with patch.object(
            ethical_hacking.socket, "getaddrinfo",
            return_value=[(None, None, None, None, ("127.0.0.1", 443))],
        ):
            result = ethical_hacking.check_website_security("https://example.com")
        self.assertEqual(result["status"], "error")
        self.assertIn("blocked", result["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
