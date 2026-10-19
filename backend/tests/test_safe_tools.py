"""Tests for the deterministic, allowlisted NOX utility tools."""
import unittest

from backend.safe_tools import SafeToolError, run_tool


class SafeToolTests(unittest.TestCase):
    def test_calculator_handles_basic_arithmetic_and_precedence(self):
        result = run_tool("calculator", "(125 * 8) / 4")
        self.assertEqual(result["result"], 250)

    def test_calculator_rejects_python_calls_and_names(self):
        for expression in ("__import__('os').system('echo unsafe')", "open('secret')", "x + 1"):
            with self.subTest(expression=expression), self.assertRaises(SafeToolError):
                run_tool("calculator", expression)

    def test_calculator_rejects_division_by_zero_and_unbounded_exponents(self):
        for expression in ("1 / 0", "10000000 ** 11"):
            with self.subTest(expression=expression), self.assertRaises(SafeToolError):
                run_tool("calculator", expression)

    def test_text_analysis_counts_words_case_insensitively(self):
        result = run_tool("text_analysis", "Hello hello\nworld!")
        self.assertEqual(result["words"], 3)
        self.assertEqual(result["unique_words"], 2)
        self.assertEqual(result["top_words"][0], {"word": "hello", "count": 2})
        self.assertEqual(result["lines"], 2)

    def test_json_validator_formats_valid_json_and_reports_keys(self):
        result = run_tool("json_validator", '{"name":"NOX","active":true}')
        self.assertTrue(result["valid"])
        self.assertEqual(result["value_type"], "object")
        self.assertEqual(result["top_level_keys"], ["name", "active"])
        self.assertIn('\n  "name": "NOX"', result["formatted"])

    def test_json_validator_rejects_invalid_and_nonstandard_constants(self):
        for raw in ('{"x":}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(SafeToolError):
                run_tool("json_validator", raw)

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(SafeToolError):
            run_tool("shell", "echo hello")


if __name__ == "__main__":
    unittest.main()
