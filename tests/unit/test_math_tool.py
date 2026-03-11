from __future__ import annotations
import pytest

from app.infrastructure.tools.math_tool import MathTool


@pytest.fixture
def math_tool():
    return MathTool()


@pytest.mark.asyncio
async def test_simple_addition(math_tool):
    result = await math_tool.execute({"expression": "2 + 3"})
    assert result.status == "success"
    assert result.result["value"] == 5.0


@pytest.mark.asyncio
async def test_multiplication(math_tool):
    result = await math_tool.execute({"expression": "25 * 4"})
    assert result.status == "success"
    assert result.result["value"] == 100.0


@pytest.mark.asyncio
async def test_complex_expression(math_tool):
    result = await math_tool.execute({"expression": "(10 + 5) * 3 - 2"})
    assert result.status == "success"
    assert result.result["value"] == 43.0


@pytest.mark.asyncio
async def test_division(math_tool):
    result = await math_tool.execute({"expression": "100 / 4"})
    assert result.status == "success"
    assert result.result["value"] == 25.0


@pytest.mark.asyncio
async def test_power(math_tool):
    result = await math_tool.execute({"expression": "2 ** 10"})
    assert result.status == "success"
    assert result.result["value"] == 1024.0


@pytest.mark.asyncio
async def test_floor_division(math_tool):
    result = await math_tool.execute({"expression": "7 // 2"})
    assert result.status == "success"
    assert result.result["value"] == 3.0


@pytest.mark.asyncio
async def test_modulo(math_tool):
    result = await math_tool.execute({"expression": "10 % 3"})
    assert result.status == "success"
    assert result.result["value"] == 1.0


@pytest.mark.asyncio
async def test_negative_numbers(math_tool):
    result = await math_tool.execute({"expression": "-5 + 3"})
    assert result.status == "success"
    assert result.result["value"] == -2.0


@pytest.mark.asyncio
async def test_division_by_zero(math_tool):
    result = await math_tool.execute({"expression": "10 / 0"})
    assert result.status == "error"
    assert "Division by zero" in result.error


@pytest.mark.asyncio
async def test_invalid_expression(math_tool):
    result = await math_tool.execute({"expression": "import os"})
    assert result.status == "error"


@pytest.mark.asyncio
async def test_missing_expression(math_tool):
    result = await math_tool.execute({})
    assert result.status == "validation_error"


@pytest.mark.asyncio
async def test_empty_expression(math_tool):
    result = await math_tool.execute({"expression": ""})
    assert result.status == "validation_error"


@pytest.mark.asyncio
async def test_large_exponent_rejected(math_tool):
    result = await math_tool.execute({"expression": "2 ** 10000"})
    assert result.status == "error"
    assert "too large" in result.error.lower() or "Exponent" in result.error


@pytest.mark.asyncio
async def test_tool_name(math_tool):
    assert math_tool.name() == "math"


@pytest.mark.asyncio
async def test_tool_description(math_tool):
    assert "arithmetic" in math_tool.description().lower()


@pytest.mark.asyncio
async def test_parameters_schema(math_tool):
    schema = math_tool.parameters_schema()
    assert "expression" in schema["properties"]
    assert "expression" in schema["required"]
