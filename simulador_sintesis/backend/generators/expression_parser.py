import re
from dataclasses import dataclass
from typing import List, Union


@dataclass
class ExprNode:
    value: str
    left: Union["ExprNode", None] = None
    right: Union["ExprNode", None] = None
    is_unary: bool = False

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None and not self.is_unary

    def required_registers(self) -> int:
        if self.is_leaf:
            return 1
        if self.is_unary:
            return self.right.required_registers() if self.right else 1
        l_req = self.left.required_registers() if self.left else 0
        r_req = self.right.required_registers() if self.right else 0
        if l_req == r_req:
            return l_req + 1
        return max(l_req, r_req)


class ExpressionParser:
    PRECEDENCE = {
        "==": 0, "!=": 0, "<": 0, ">": 0, "<=": 0, ">=": 0,
        "+": 1, "-": 1,
        "*": 2, "/": 2, "%": 2,
        ".": 3,
        "!": 4,
    }

    TOKEN_REGEX = re.compile(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\d+\.\d+[fF]?|\d+[fF]?|\+\+|--|>=|<=|==|!=|[A-Za-z_]\w*(?:\(\))?|[+\-*/%.!<>()]'
    )

    @classmethod
    def preprocess_sugar(cls, expr: str) -> str:
        expr = re.sub(r"\(\s*(?:float|double|int|char|long|short|byte|boolean)\s*\)", "", expr)
        expr = re.sub(r"\bMath\s*\.\s*random\s*\(\s*\)", "Math . random()", expr)
        expr = re.sub(r"\.\s*length\s*\(\s*\)", " . length()", expr)
        expr = re.sub(r"\+\+\s*(ID\d+|[A-Za-z_]\w*)", r"(1 + \1)", expr)
        expr = re.sub(r"(ID\d+|[A-Za-z_]\w*)\s*\+\+", r"(\1 + 1)", expr)
        expr = re.sub(r"--\s*(ID\d+|[A-Za-z_]\w*)", r"(\1 - 1)", expr)
        expr = re.sub(r"(ID\d+|[A-Za-z_]\w*)\s*--", r"(\1 - 1)", expr)
        return expr.strip()

    @classmethod
    def tokenize(cls, expr: str) -> List[str]:
        expr = cls.preprocess_sugar(expr)
        raw_tokens = cls.TOKEN_REGEX.findall(expr)
        tokens: List[str] = []
        for i, tok in enumerate(raw_tokens):
            if tok == "-" and (
                i == 0 or raw_tokens[i - 1] in ("(", "+", "-", "*", "/", "%", "!", ">=", "<=", "==", "!=", "<", ">")
            ):
                tokens.append("0")
                tokens.append("-")
            else:
                tokens.append(tok)
        return tokens

    @classmethod
    def to_postfix(cls, expr: str) -> List[str]:
        tokens = cls.tokenize(expr)
        output: List[str] = []
        stack: List[str] = []

        for tok in tokens:
            if tok == "!":
                while stack and stack[-1] in cls.PRECEDENCE and cls.PRECEDENCE[stack[-1]] > cls.PRECEDENCE[tok]:
                    output.append(stack.pop())
                stack.append(tok)
            elif tok in cls.PRECEDENCE:
                while (
                    stack
                    and stack[-1] in cls.PRECEDENCE
                    and cls.PRECEDENCE[stack[-1]] >= cls.PRECEDENCE[tok]
                ):
                    output.append(stack.pop())
                stack.append(tok)
            elif tok == "(":
                stack.append(tok)
            elif tok == ")":
                while stack and stack[-1] != "(":
                    output.append(stack.pop())
                if not stack:
                    raise ValueError(f"Paréntesis desbalanceados en expresión: {expr}")
                stack.pop()
            else:
                output.append(tok)

        while stack:
            op = stack.pop()
            if op in ("(", ")"):
                raise ValueError(f"Paréntesis desbalanceados en expresión: {expr}")
            output.append(op)

        return output

    @classmethod
    def build_ast(cls, expr: str) -> ExprNode:
        postfix = cls.to_postfix(expr)
        stack: List[ExprNode] = []

        for tok in postfix:
            if tok == "!":
                if not stack:
                    raise ValueError(f"Expresión mal formada: {expr}")
                operand = stack.pop()
                stack.append(ExprNode(value="!", right=operand, is_unary=True))
            elif tok in cls.PRECEDENCE:
                if len(stack) < 2:
                    raise ValueError(f"Expresión mal formada: {expr}")
                right = stack.pop()
                left = stack.pop()
                stack.append(ExprNode(value=tok, left=left, right=right))
            else:
                stack.append(ExprNode(value=tok))

        if len(stack) != 1:
            raise ValueError(f"No se pudo construir el árbol de expresión para: {expr}")
        return stack[0]