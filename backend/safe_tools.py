"""Small deterministic tools with no shell, filesystem, network, or model access."""
from __future__ import annotations

import ast
import json
import math
import operator
import re
from collections import Counter
from typing import Any


class SafeToolError(ValueError):
    """Input is invalid or outside the bounded tool contract."""


_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _number(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        value = node.value
        if not math.isfinite(value) or abs(value) > 1e12:
            raise SafeToolError("Numbers must be finite and no larger than 1e12 in magnitude.")
        return value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_number(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _number(node.left), _number(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 10 or abs(left) > 1e6):
            raise SafeToolError("Exponentiation is bounded to exponents up to 10 and bases up to 1e6.")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise SafeToolError("Division by zero is not allowed.")
        try:
            value = _BINOPS[type(node.op)](left, right)
        except (OverflowError, ZeroDivisionError, ValueError) as exc:
            raise SafeToolError("That calculation is outside the supported range.") from exc
        if not isinstance(value, (int, float)) or abs(value) > 1e100 or (isinstance(value, float) and not math.isfinite(value)):
            raise SafeToolError("Result is outside the supported numeric range.")
        return value
    raise SafeToolError("Use only numbers, parentheses, and +, -, *, /, //, %, ** operators.")


def calculate(expression: str) -> dict[str, Any]:
    expression = expression.strip()
    if not expression or len(expression) > 200:
        raise SafeToolError("Enter a calculation between 1 and 200 characters.")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise SafeToolError("The expression could not be parsed.") from exc
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise SafeToolError("Expression is too complex.")
    result = _number(tree.body)
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e16:
        result = int(result)
    formatted = format(result, ",.12g") if isinstance(result, float) else f"{result:,}"
    return {"tool": "calculator", "result": result, "formatted": formatted}


def analyze_text(value: str) -> dict[str, Any]:
    if len(value) > 10000:
        raise SafeToolError("Text is limited to 10,000 characters.")
    words = re.findall(r"\b[\w’'-]+\b", value, flags=re.UNICODE)
    normalized = [word.casefold() for word in words]
    return {
        "tool": "text_analysis",
        "characters": len(value),
        "characters_without_whitespace": sum(not char.isspace() for char in value),
        "words": len(words),
        "lines": len(value.splitlines()) if value else 0,
        "unique_words": len(set(normalized)),
        "top_words": [{"word": word, "count": count} for word, count in Counter(normalized).most_common(8)],
        "estimated_reading_minutes": round(len(words) / 200, 2),
    }


def _reject_json_constant(value: str):
    raise SafeToolError("JSON must not contain NaN or Infinity; use standard JSON values.")


def validate_json(value: str) -> dict[str, Any]:
    if len(value) > 10000:
        raise SafeToolError("JSON input is limited to 10,000 characters.")
    if not value.strip():
        raise SafeToolError("Paste JSON to validate or format.")
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise SafeToolError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    pretty = json.dumps(parsed, ensure_ascii=False, indent=2, allow_nan=False)
    kind = "null" if parsed is None else (
        "array" if isinstance(parsed, list) else
        "object" if isinstance(parsed, dict) else type(parsed).__name__
    )
    return {
        "tool": "json_validator", "valid": True, "value_type": kind,
        "top_level_keys": list(parsed.keys())[:50] if isinstance(parsed, dict) else [],
        "formatted": pretty[:12000],
    }


def run_tool(name: str, value: str) -> dict[str, Any]:
    if not isinstance(value, str):
        raise SafeToolError("Tool input must be text.")
    if name == "calculator":
        return calculate(value)
    if name == "text_analysis":
        return analyze_text(value)
    if name == "json_validator":
        return validate_json(value)
    raise SafeToolError("Unknown tool. Available tools: calculator, text_analysis, json_validator.")
