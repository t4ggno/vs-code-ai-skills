from __future__ import annotations

import ast
import math
import operator
import sys
from typing import Any, Callable

SAFE_NAMES: dict[str, Any] = {
    "math": math,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
    "nan": math.nan,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
    "degrees": math.degrees,
    "radians": math.radians,
    "hypot": math.hypot,
}

BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def is_supported_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def resolve_name(name: str) -> Any:
    if name in SAFE_NAMES:
        return SAFE_NAMES[name]
    raise ValueError(f"Unsupported name '{name}'.")


def resolve_math_attribute(attribute_name: str) -> Any:
    if attribute_name.startswith("_"):
        raise ValueError("Private math attributes are not allowed.")
    if not hasattr(math, attribute_name):
        raise ValueError(f"Unknown math attribute '{attribute_name}'.")
    return getattr(math, attribute_name)


def evaluate_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return evaluate_node(node.body)

    if isinstance(node, ast.Constant):
        if is_supported_number(node.value):
            return node.value
        raise ValueError("Only numeric literals are allowed.")

    if isinstance(node, ast.Name):
        return resolve_name(node.id)

    if isinstance(node, ast.Attribute):
        value = evaluate_node(node.value)
        if value is not math:
            raise ValueError("Only math.<name> attribute access is allowed.")
        return resolve_math_attribute(node.attr)

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.BitXor):
            raise ValueError("Use ** for exponentiation instead of ^.")
        operator_fn = BINARY_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise ValueError(f"Unsupported operator '{type(node.op).__name__}'.")
        return operator_fn(evaluate_node(node.left), evaluate_node(node.right))

    if isinstance(node, ast.UnaryOp):
        operator_fn = UNARY_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise ValueError(f"Unsupported unary operator '{type(node.op).__name__}'.")
        return operator_fn(evaluate_node(node.operand))

    if isinstance(node, ast.Call):
        function = evaluate_node(node.func)
        if not callable(function):
            raise ValueError("Only callable functions can be invoked.")
        if any(keyword.arg is None for keyword in node.keywords):
            raise ValueError("Starred keyword arguments are not allowed.")
        args = [evaluate_node(argument) for argument in node.args]
        kwargs = {
            keyword.arg: evaluate_node(keyword.value)
            for keyword in node.keywords
            if keyword.arg is not None
        }
        return function(*args, **kwargs)

    raise ValueError(f"Unsupported expression element '{type(node).__name__}'.")


def calculate(expression: str) -> Any:
    try:
        parsed = ast.parse(expression, mode="eval")
        result = evaluate_node(parsed)
        if callable(result) or result is math:
            raise ValueError("Expression must resolve to a numeric value.")
        return result
    except Exception as exc:
        return f"Error evaluating expression: {exc}"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python calculate.py '<math_expression>'")
        return 1

    expression = sys.argv[1]
    print(f"Result: {calculate(expression)}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        raise SystemExit(exit_code)
