from typing import List, Set
from backend.entities.intermediate_code import Triplo, Cuadruplo, TresDirecciones
from backend.generators.expression_parser import ExpressionParser, ExprNode


class IntermediateCodeGenerator:
    """Genera Triplos, Cuádruplos y Código de Tres Direcciones (1 <= n <= 3)."""

    def generate_triplos(self, cleaned_statements: List[str]) -> List[Triplo]:
        triplos: List[Triplo] = []
        idx = 1

        for stmt in cleaned_statements:
            if stmt.startswith("PRINT "):
                expr = stmt[6:].strip()
                res_ref, idx = self._emit_triplos_expr(expr, triplos, idx)
                triplos.append(Triplo(indice=idx, val1="SOUT", ope="print", val2=res_ref))
                idx += 1
                continue

            var_name, expr = [part.strip() for part in stmt.split("=", 1)]
            res_ref, idx = self._emit_triplos_expr(expr, triplos, idx)
            triplos.append(Triplo(indice=idx, val1=var_name, ope="=", val2=res_ref))
            idx += 1

        return triplos

    def _emit_triplos_expr(self, expr: str, triplos: List[Triplo], idx: int):
        postfix = ExpressionParser.to_postfix(expr)
        stack: List[str] = []

        for tok in postfix:
            if tok in ExpressionParser.PRECEDENCE:
                val2 = stack.pop()
                val1 = stack.pop()
                triplos.append(Triplo(indice=idx, val1=val1, ope=tok, val2=val2))
                stack.append(f"[{idx}]")
                idx += 1
            else:
                stack.append(tok)

        return stack[0], idx

    def generate_cuadruplos(self, cleaned_statements: List[str]) -> List[Cuadruplo]:
        cuadruplos: List[Cuadruplo] = []
        idx = 1
        temp_count = 1

        for stmt in cleaned_statements:
            if stmt.startswith("PRINT "):
                expr = stmt[6:].strip()
                res_ref, idx, temp_count = self._emit_cuadruplos_expr(expr, cuadruplos, idx, temp_count)
                cuadruplos.append(Cuadruplo(indice=idx, val1=res_ref, ope="SOUT", val2="-", res="CONSOLA"))
                idx += 1
                continue

            var_name, expr = [part.strip() for part in stmt.split("=", 1)]
            res_ref, idx, temp_count = self._emit_cuadruplos_expr(expr, cuadruplos, idx, temp_count)
            cuadruplos.append(Cuadruplo(indice=idx, val1=res_ref, ope="=", val2="-", res=var_name))
            idx += 1

        return cuadruplos

    def _emit_cuadruplos_expr(self, expr: str, cuadruplos: List[Cuadruplo], idx: int, temp_count: int):
        postfix = ExpressionParser.to_postfix(expr)
        stack: List[str] = []

        for tok in postfix:
            if tok in ExpressionParser.PRECEDENCE:
                val2 = stack.pop()
                val1 = stack.pop()
                temp_name = f"T{temp_count}"
                temp_count += 1
                cuadruplos.append(Cuadruplo(indice=idx, val1=val1, ope=tok, val2=val2, res=temp_name))
                stack.append(temp_name)
                idx += 1
            else:
                stack.append(tok)

        return stack[0], idx, temp_count

    def generate_tres_direcciones(self, cleaned_statements: List[str]) -> List[TresDirecciones]:
        """
        Genera Código de Tres Direcciones restringido estrictamente a 3 registros (T1, T2, T3).
        Utiliza ordenamiento de Sethi-Ullman y liberación inmediata de temporales.
        """
        instrucciones: List[TresDirecciones] = []

        for stmt in cleaned_statements:
            available_regs: Set[int] = {1, 2, 3}

            if stmt.startswith("PRINT "):
                expr = stmt[6:].strip()
                ast = ExpressionParser.build_ast(expr)
                val_ref, reg_used = self._eval_ast_3dir(ast, available_regs, instrucciones)
                target_reg = reg_used if reg_used is not None else self._alloc_reg(available_regs)
                instrucciones.append(TresDirecciones(registro=target_reg, val1="SOUT", ope="", val2=val_ref))
                continue

            var_name, expr = [part.strip() for part in stmt.split("=", 1)]
            ast = ExpressionParser.build_ast(expr)
            val_ref, reg_used = self._eval_ast_3dir(ast, available_regs, instrucciones)

            target_reg = reg_used if reg_used is not None else self._alloc_reg(available_regs)
            instrucciones.append(
                TresDirecciones(registro=target_reg, val1=var_name, ope="=", val2=val_ref)
            )

        return instrucciones

    def _alloc_reg(self, available_regs: Set[int]) -> int:
        if not available_regs:
            raise ValueError(
                "Límite de registros excedido: la expresión requiere más de 3 registros simultáneos (1 <= n <= 3)."
            )
        reg = min(available_regs)
        available_regs.remove(reg)
        return reg

    def _eval_ast_3dir(
        self,
        node: ExprNode,
        available_regs: Set[int],
        instrucciones: List[TresDirecciones],
    ):
        if node.is_leaf:
            return node.value, None

        left_req = node.left.required_registers()
        right_req = node.right.required_registers()

        # Evaluar primero el subárbol más pesado para no agotar T1..T3
        if right_req > left_req:
            val2, reg2 = self._eval_ast_3dir(node.right, available_regs, instrucciones)
            val1, reg1 = self._eval_ast_3dir(node.left, available_regs, instrucciones)
        else:
            val1, reg1 = self._eval_ast_3dir(node.left, available_regs, instrucciones)
            val2, reg2 = self._eval_ast_3dir(node.right, available_regs, instrucciones)

        # Reutilizar registro de operando izquierdo o derecho y liberar el sobrante
        if reg1 is not None:
            dest_reg = reg1
            if reg2 is not None:
                available_regs.add(reg2)
        elif reg2 is not None:
            dest_reg = reg2
        else:
            dest_reg = self._alloc_reg(available_regs)

        instrucciones.append(
            TresDirecciones(registro=dest_reg, val1=val1, ope=node.value, val2=val2)
        )
        return f"T{dest_reg}", dest_reg