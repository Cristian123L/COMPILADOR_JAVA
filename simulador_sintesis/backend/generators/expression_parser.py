import re
from dataclasses import dataclass
from typing import List, Union


@dataclass
class ExprNode:
    value: str
    left: Union["ExprNode", None] = None
    right: Union["ExprNode", None] = None

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None

    def required_registers(self) -> int:
        """Número de Sethi-Ullman para minimizar registros temporales (1 <= n <= 3)."""
        if self.is_leaf:
            return 1
        l_req = self.left.required_registers() if self.left else 0
        r_req = self.right.required_registers() if self.right else 0
        if l_req == r_req:
            return l_req + 1
        return max(l_req, r_req)


class ExpressionParser:
    PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "%": 2}
    TOKEN_REGEX = re.compile(r"\d+\.\d+|\d+|[A-Za-z_]\w*|[+\-*/%()]")

    @classmethod
    def tokenize(cls, expr: str) -> List[str]:
        raw_tokens = cls.TOKEN_REGEX.findall(expr)
        tokens: List[str] = []
        for i, tok in enumerate(raw_tokens):
            # Manejar signo unario negativo (ej: -5 o (-x))
            if tok == "-" and (i == 0 or raw_tokens[i - 1] in ("(", "+", "-", "*", "/", "%")):
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
            if tok in cls.PRECEDENCE:
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
            if tok in cls.PRECEDENCE:
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