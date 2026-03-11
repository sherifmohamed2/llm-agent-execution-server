from __future__ import annotations
import ast
import operator
import time
from typing import Any

from app.core.exceptions import ToolExecutionError, ToolValidationError
from app.domain.enums.status import ToolCallStatus
from app.domain.enums.tool_name import ToolName
from app.domain.interfaces.tool import ToolInterface
from app.domain.models.tool_call import ToolCallResult

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

MAX_POWER = 1000


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ToolValidationError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type is ast.Pow and right > MAX_POWER:
            raise ToolValidationError(f"Exponent too large (max {MAX_POWER})")
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise ToolExecutionError("Division by zero")
        return SAFE_OPERATORS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ToolValidationError(f"Unsupported unary operator: {op_type.__name__}")
        return SAFE_OPERATORS[op_type](_safe_eval(node.operand))

    raise ToolValidationError(
        f"Unsupported expression node: {type(node).__name__}"
    )


class MathTool(ToolInterface):
    def name(self) -> str:
        return ToolName.MATH.value

    def description(self) -> str:
        return "Evaluate a safe arithmetic expression (no code execution). Supports +, -, *, /, //, %, **."

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression to evaluate, e.g. '25 * 4 + 10'",
                }
            },
            "required": ["expression"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolCallResult:
        start = time.perf_counter()
        expression = arguments.get("expression", "")

        if not expression or not isinstance(expression, str):
            return ToolCallResult(
                tool_name=self.name(),
                call_id=None,
                status=ToolCallStatus.VALIDATION_ERROR.value,
                error="Missing or invalid 'expression' argument",
            )

        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree)
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolCallResult(
                tool_name=self.name(),
                call_id=None,
                status=ToolCallStatus.SUCCESS.value,
                result={"expression": expression, "value": result},
                duration_ms=round(duration_ms, 2),
            )
        except (ToolValidationError, ToolExecutionError) as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolCallResult(
                tool_name=self.name(),
                call_id=None,
                status=ToolCallStatus.ERROR.value,
                error=str(exc),
                duration_ms=round(duration_ms, 2),
            )
        except (SyntaxError, ValueError, TypeError) as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolCallResult(
                tool_name=self.name(),
                call_id=None,
                status=ToolCallStatus.ERROR.value,
                error=f"Invalid expression: {exc}",
                duration_ms=round(duration_ms, 2),
            )
