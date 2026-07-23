import ast
import re
from fractions import Fraction

from backend.app.schemas.analysis import VerificationResult

ARITHMETIC_PATTERN = re.compile(r"(?<![\w.])(?:\d+(?:\.\d+)?\s*[+\-*/]\s*)+\d+(?:\.\d+)?")
ANSWER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?")


class UnsupportedExpression(ValueError):
    pass


def evaluate(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Expression):
        return evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Fraction(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -evaluate(node.operand)
    if isinstance(node, ast.BinOp):
        left = evaluate(node.left)
        right = evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise UnsupportedExpression


def parse_number(value: str) -> Fraction:
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return Fraction(numerator) / Fraction(denominator)
    return Fraction(value)


def verify_simple_arithmetic(question: str, final_answer: str) -> VerificationResult:
    expressions = ARITHMETIC_PATTERN.findall(question.replace("×", "*").replace("÷", "/"))
    answers = ANSWER_PATTERN.findall(final_answer)
    if not expressions or not answers:
        return VerificationResult(
            status="not_applicable",
            message="当前题型暂不适用简单算术自动校验，请人工核对。",
        )

    expression = max(expressions, key=len).strip()
    try:
        expected = evaluate(ast.parse(expression, mode="eval"))
        actual = parse_number(answers[0])
    except (ArithmeticError, SyntaxError, UnsupportedExpression, ValueError, ZeroDivisionError):
        return VerificationResult(
            status="verification_failed",
            message="自动校验未能可靠计算该表达式，请人工核对。",
        )

    expected_text = str(expected.numerator) if expected.denominator == 1 else str(expected)
    if expected == actual:
        return VerificationResult(
            status="verified", message=f"简单算术校验通过：结果为 {expected_text}。"
        )
    return VerificationResult(
        status="conflict",
        message=f"自动校验发现不一致：简单算术结果应为 {expected_text}，请重新分析或人工核对。",
    )
