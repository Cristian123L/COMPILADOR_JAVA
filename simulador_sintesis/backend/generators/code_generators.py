import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from backend.entities.intermediate_code import Cuadruplo, TresDirecciones, Triplo
from backend.entities.symbol_entry import SymbolEntry
from backend.generators.expression_parser import ExprNode, ExpressionParser
from backend.validator.java_validator import IRInstruction


@dataclass
class TypedVal:
    raw_val: object
    vtype: str  # int, float, double, char, String, boolean

    def format_res(self) -> str:
        if self.vtype == "float":
            num = float(self.raw_val)
            txt = f"{num:.6f}".rstrip("0").rstrip(".")
            if "." not in txt:
                txt += ".0"
            return f"{txt}f"
        if self.vtype == "double":
            num = float(self.raw_val)
            txt = f"{num:.8f}".rstrip("0").rstrip(".")
            if "." not in txt:
                txt += ".0"
            return txt
        if self.vtype == "int":
            return str(int(self.raw_val))
        if self.vtype == "char":
            if isinstance(self.raw_val, int):
                return f"'{chr(self.raw_val)}'"
            return f"'{self.raw_val}'"
        if self.vtype == "String":
            s = str(self.raw_val)
            return s if (s.startswith('"') and s.endswith('"')) else f'"{s}"'
        return str(self.raw_val)


@dataclass
class ExecStepNode:
    """Nodo ejecutable dentro del Árbol Abstracto-Semántico unificado."""
    uid: int
    kind: str                          # OP, ASSIGN, RTN, SOUT, CALL, CALL_SOUT
    ope: str
    target_id: str = ""
    target_type: str = ""
    left_tok: str = ""
    right_tok: str = ""
    left_node: Optional["ExecStepNode"] = None
    right_node: Optional["ExecStepNode"] = None
    children: List["ExecStepNode"] = field(default_factory=list)
    root_id: int = 0
    depth: int = 0
    lr_order: int = 0


class IntermediateCodeGenerator:
    def _build_bottom_up_plan(
        self,
        instructions: List[IRInstruction],
        defer_pending_for_3dir: bool = False,
    ) -> List[ExecStepNode]:
        uid_counter = 0

        def next_uid() -> int:
            nonlocal uid_counter
            uid_counter += 1
            return uid_counter

        latest_def: Dict[str, ExecStepNode] = {}
        expanded_defs: Set[int] = set()
        inst_nodes: List[ExecStepNode] = []

        def convert_expr(expr_node: ExprNode) -> Tuple[str, Optional[ExecStepNode]]:
            if expr_node.is_leaf:
                tok = expr_node.value
                if tok in latest_def:
                    def_node = latest_def[tok]
                    if def_node.uid not in expanded_defs:
                        expanded_defs.add(def_node.uid)
                        return tok, def_node
                return tok, None

            l_tok, l_sub = convert_expr(expr_node.left)
            r_tok, r_sub = convert_expr(expr_node.right)
            kids: List[ExecStepNode] = []
            if l_sub is not None:
                kids.append(l_sub)
            if r_sub is not None:
                kids.append(r_sub)

            op_node = ExecStepNode(
                uid=next_uid(),
                kind="OP",
                ope=expr_node.value,
                left_tok=l_tok,
                right_tok=r_tok,
                left_node=l_sub,
                right_node=r_sub,
                children=kids,
            )
            return "", op_node

        for inst in instructions:
            if inst.kind in ("ASSIGN", "RTN", "SOUT"):
                ast = ExpressionParser.build_ast(inst.expr)
                val_tok, sub_node = convert_expr(ast)
                kids = [sub_node] if sub_node is not None else []
                node = ExecStepNode(
                    uid=next_uid(),
                    kind=inst.kind,
                    ope="=" if inst.kind == "ASSIGN" else inst.kind,
                    target_id=inst.target_id,
                    target_type=inst.target_type,
                    left_tok=inst.target_id,
                    right_tok=val_tok,
                    right_node=sub_node,
                    children=kids,
                )
                inst_nodes.append(node)
                if inst.kind == "ASSIGN":
                    latest_def[inst.target_id] = node
                elif inst.kind == "RTN":
                    latest_def[inst.target_id] = node
                elif inst.kind == "SOUT" and inst.method_owner_id:
                    latest_def[inst.method_owner_id] = node

            elif inst.kind == "CALL":
                target_def = latest_def.get(inst.expr)
                kids = []
                if target_def is not None and target_def.uid not in expanded_defs:
                    expanded_defs.add(target_def.uid)
                    kids.append(target_def)
                node = ExecStepNode(
                    uid=next_uid(),
                    kind="CALL",
                    ope=".",
                    target_id=inst.target_id,
                    target_type=inst.target_type,
                    left_tok=inst.target_id,
                    right_tok=inst.expr,
                    right_node=target_def,
                    children=kids,
                )
                inst_nodes.append(node)

            elif inst.kind == "CALL_SOUT":
                target_def = latest_def.get(inst.expr)
                kids = []
                if target_def is not None and target_def.uid not in expanded_defs:
                    expanded_defs.add(target_def.uid)
                    kids.append(target_def)
                call_node = ExecStepNode(
                    uid=next_uid(),
                    kind="CALL",
                    ope=".",
                    target_id=inst.target_id,
                    target_type=inst.target_type,
                    left_tok=inst.target_id,
                    right_tok=inst.expr,
                    right_node=target_def,
                    children=kids,
                )
                sout_node = ExecStepNode(
                    uid=next_uid(),
                    kind="CALL_SOUT",
                    ope="SOUT",
                    target_id="PMAIN",
                    target_type=inst.target_type,
                    left_tok="PMAIN",
                    right_node=call_node,
                    children=[call_node],
                )
                inst_nodes.append(call_node)
                inst_nodes.append(sout_node)

        roots = [n for n in inst_nodes if n.uid not in expanded_defs]
        ordered_nodes: List[ExecStepNode] = []
        visited: Set[int] = set()

        if defer_pending_for_3dir:
            def reg_demand(node: Optional[ExecStepNode]) -> int:
                if node is None:
                    return 0
                if node.kind == "OP":
                    l_req = reg_demand(node.left_node)
                    r_req = reg_demand(node.right_node)
                    if l_req == 0 and r_req == 0:
                        return 1
                    return max(l_req, r_req) + 1 if l_req == r_req else max(l_req, r_req)
                if node.right_node is not None:
                    return reg_demand(node.right_node)
                return 0

            def emit_postorder_3dir(node: ExecStepNode, acc: List[ExecStepNode]):
                if node.uid in visited:
                    return
                visited.add(node.uid)
                if node.kind == "OP":
                    l_req = reg_demand(node.left_node)
                    r_req = reg_demand(node.right_node)
                    if r_req > l_req:
                        if node.right_node is not None:
                            emit_postorder_3dir(node.right_node, acc)
                        if node.left_node is not None:
                            emit_postorder_3dir(node.left_node, acc)
                    else:
                        if node.left_node is not None:
                            emit_postorder_3dir(node.left_node, acc)
                        if node.right_node is not None:
                            emit_postorder_3dir(node.right_node, acc)
                else:
                    for child in node.children:
                        emit_postorder_3dir(child, acc)
                acc.append(node)

            for root in roots:
                emit_postorder_3dir(root, ordered_nodes)
            return ordered_nodes

        lr_counter = 0

        def collect(node: ExecStepNode, root_id: int, depth: int, acc: List[ExecStepNode]):
            nonlocal lr_counter
            if node.uid in visited:
                return
            visited.add(node.uid)
            node.root_id = root_id
            node.depth = depth
            node.lr_order = lr_counter
            lr_counter += 1
            acc.append(node)
            for child in node.children:
                collect(child, root_id, depth + 1, acc)

        for r_idx, root in enumerate(roots):
            tree_nodes: List[ExecStepNode] = []
            collect(root, r_idx, 0, tree_nodes)
            tree_nodes.sort(key=lambda n: (-n.depth, n.lr_order))
            ordered_nodes.extend(tree_nodes)

        return ordered_nodes

    def generate_triplos(
        self,
        instructions: List[IRInstruction],
        main_class_id: str = "ID1",
    ) -> Tuple[List[Triplo], str]:
        plan = self._build_bottom_up_plan(instructions, defer_pending_for_3dir=False)
        triplos: List[Triplo] = []
        node_ref: Dict[int, str] = {}
        last_id_ref: Dict[str, str] = {}
        idx = 1

        for node in plan:
            if node.kind == "OP":
                v1 = node_ref[node.left_node.uid] if node.left_node else last_id_ref.get(node.left_tok, node.left_tok)
                v2 = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                triplos.append(Triplo(indice=idx, val1=v1, ope=node.ope, val2=v2))
                node_ref[node.uid] = f"[{idx}]"
                idx += 1

            elif node.kind in ("ASSIGN", "RTN", "SOUT"):
                v2 = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                triplos.append(Triplo(indice=idx, val1=node.target_id, ope=node.ope, val2=v2))
                ref = f"[{idx}]"
                node_ref[node.uid] = ref
                last_id_ref[node.target_id] = ref
                idx += 1

            elif node.kind == "CALL":
                v2 = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                triplos.append(Triplo(indice=idx, val1=node.target_id, ope=".", val2=v2))
                node_ref[node.uid] = f"[{idx}]"
                idx += 1

            elif node.kind == "CALL_SOUT":
                v2 = node_ref[node.right_node.uid] if node.right_node else f"[{idx - 1}]"
                triplos.append(Triplo(indice=idx, val1="PMAIN", ope="SOUT", val2=v2))
                node_ref[node.uid] = f"[{idx}]"
                idx += 1

        last_n = idx - 1
        footer = f"{main_class_id} PMAIN -> [{last_n}]" if last_n >= 1 else ""
        return triplos, footer

    def generate_cuadruplos(
        self,
        instructions: List[IRInstruction],
        symbols: List[SymbolEntry],
        main_class_id: str = "ID1",
    ) -> Tuple[List[Cuadruplo], str]:
        plan = self._build_bottom_up_plan(instructions, defer_pending_for_3dir=False)
        cuadruplos: List[Cuadruplo] = []
        node_ref: Dict[int, str] = {}
        node_val: Dict[int, TypedVal] = {}
        last_id_ref: Dict[str, str] = {}
        env: Dict[str, TypedVal] = {}
        idx = 1

        for node in plan:
            if node.kind == "OP":
                v1_ref = node_ref[node.left_node.uid] if node.left_node else last_id_ref.get(node.left_tok, node.left_tok)
                v2_ref = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                tv1 = node_val[node.left_node.uid] if node.left_node else self._literal_or_id_to_typed(node.left_tok, env)
                tv2 = node_val[node.right_node.uid] if node.right_node else self._literal_or_id_to_typed(node.right_tok, env)

                res_tv = self._eval_binary_typed(tv1, node.ope, tv2)
                cuadruplos.append(
                    Cuadruplo(indice=idx, val1=v1_ref, ope=node.ope, val2=v2_ref, res=res_tv.format_res())
                )
                node_ref[node.uid] = f"[{idx}]"
                node_val[node.uid] = res_tv
                idx += 1

            elif node.kind == "ASSIGN":
                v2_ref = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                tv2 = node_val[node.right_node.uid] if node.right_node else self._literal_or_id_to_typed(node.right_tok, env)
                casted = self._coerce_to_target(tv2, node.target_type)
                env[node.target_id] = casted
                cuadruplos.append(
                    Cuadruplo(indice=idx, val1=node.target_id, ope="=", val2=v2_ref, res=casted.format_res())
                )
                ref = f"[{idx}]"
                node_ref[node.uid] = ref
                node_val[node.uid] = casted
                last_id_ref[node.target_id] = ref
                idx += 1

            elif node.kind == "RTN":
                v2_ref = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                tv2 = node_val[node.right_node.uid] if node.right_node else self._literal_or_id_to_typed(node.right_tok, env)
                casted = self._coerce_to_target(tv2, node.target_type)
                env[node.target_id] = casted
                cuadruplos.append(
                    Cuadruplo(indice=idx, val1=node.target_id, ope="RTN", val2=v2_ref, res=casted.format_res())
                )
                ref = f"[{idx}]"
                node_ref[node.uid] = ref
                node_val[node.uid] = casted
                last_id_ref[node.target_id] = ref
                idx += 1

            elif node.kind == "SOUT":
                v2_ref = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                tv2 = node_val[node.right_node.uid] if node.right_node else self._literal_or_id_to_typed(node.right_tok, env)
                env[node.target_id] = tv2
                cuadruplos.append(
                    Cuadruplo(indice=idx, val1=node.target_id, ope="SOUT", val2=v2_ref, res=tv2.format_res())
                )
                ref = f"[{idx}]"
                node_ref[node.uid] = ref
                node_val[node.uid] = tv2
                last_id_ref[node.target_id] = ref
                idx += 1

            elif node.kind == "CALL":
                v2_ref = node_ref[node.right_node.uid] if node.right_node else last_id_ref.get(node.right_tok, node.right_tok)
                tv2 = node_val[node.right_node.uid] if node.right_node else env.get(node.right_tok, TypedVal(0, "int"))
                cuadruplos.append(
                    Cuadruplo(indice=idx, val1=node.target_id, ope=".", val2=v2_ref, res=tv2.format_res())
                )
                node_ref[node.uid] = f"[{idx}]"
                node_val[node.uid] = tv2
                idx += 1

            elif node.kind == "CALL_SOUT":
                v2_ref = node_ref[node.right_node.uid] if node.right_node else f"[{idx - 1}]"
                tv2 = node_val[node.right_node.uid] if node.right_node else TypedVal(0, "int")
                cuadruplos.append(
                    Cuadruplo(indice=idx, val1="PMAIN", ope="SOUT", val2=v2_ref, res=tv2.format_res())
                )
                node_ref[node.uid] = f"[{idx}]"
                node_val[node.uid] = tv2
                idx += 1

        last_n = idx - 1
        footer = f"{main_class_id} PMAIN -> [{last_n}]" if last_n >= 1 else ""
        return cuadruplos, footer

    def generate_tres_direcciones(
        self,
        instructions: List[IRInstruction],
        main_class_id: str = "ID1",
    ) -> Tuple[List[TresDirecciones], str]:
        
        plan = self._build_bottom_up_plan(instructions, defer_pending_for_3dir=True)
        salida: List[TresDirecciones] = []
        in_use: Set[int] = set()
        preferred_reg: Optional[int] = None
        node_holder: Dict[int, str] = {}
        node_reg: Dict[int, Optional[int]] = {}
        last_holder = ""

        for node in plan:
            if node.kind == "OP":
                v1 = node_holder[node.left_node.uid] if node.left_node else node.left_tok
                v2 = node_holder[node.right_node.uid] if node.right_node else node.right_tok
                r1 = node_reg.get(node.left_node.uid) if node.left_node else None
                r2 = node_reg.get(node.right_node.uid) if node.right_node else None

                dest_reg = self._alloc_reg(in_use, preferred_reg)
                preferred_reg = None

                if r1 is not None:
                    in_use.discard(r1)
                if r2 is not None:
                    in_use.discard(r2)

                salida.append(TresDirecciones(registro=dest_reg, val1=v1, ope=node.ope, val2=v2))
                node_holder[node.uid] = f"T{dest_reg}"
                node_reg[node.uid] = dest_reg
                last_holder = f"T{dest_reg}"

            elif node.kind == "ASSIGN":
                v2 = node_holder[node.right_node.uid] if node.right_node else node.right_tok
                r2 = node_reg.get(node.right_node.uid) if node.right_node else None

                salida.append(
                    TresDirecciones(
                        registro=0,
                        val1=node.target_id,
                        ope="=",
                        val2=v2,
                        is_direct_assign=True,
                    )
                )
                if r2 is not None:
                    in_use.discard(r2)

                node_holder[node.uid] = node.target_id
                node_reg[node.uid] = None
                last_holder = node.target_id

            elif node.kind in ("RTN", "SOUT"):
                v2 = node_holder[node.right_node.uid] if node.right_node else node.right_tok
                r2 = node_reg.get(node.right_node.uid) if node.right_node else None

                dest_reg = self._alloc_reg(in_use, preferred_reg)
                salida.append(
                    TresDirecciones(
                        registro=dest_reg,
                        val1=node.target_id,
                        ope=node.kind,
                        val2=v2,
                    )
                )
                in_use.clear()
                preferred_reg = r2

                node_holder[node.uid] = node.target_id
                node_reg[node.uid] = None
                last_holder = f"T{dest_reg}"

            elif node.kind == "CALL":
                v2 = node_holder[node.right_node.uid] if node.right_node else node.right_tok
                r2 = node_reg.get(node.right_node.uid) if node.right_node else None

                dest_reg = self._alloc_reg(in_use, preferred_reg)
                preferred_reg = None
                if r2 is not None:
                    in_use.discard(r2)

                salida.append(TresDirecciones(registro=dest_reg, val1=node.target_id, ope=".", val2=v2))
                node_holder[node.uid] = f"T{dest_reg}"
                node_reg[node.uid] = dest_reg
                last_holder = f"T{dest_reg}"

            elif node.kind == "CALL_SOUT":
                v2 = node_holder[node.right_node.uid] if node.right_node else last_holder

                dest_reg = self._alloc_reg(in_use, preferred_reg)
                salida.append(TresDirecciones(registro=dest_reg, val1="PMAIN", ope="SOUT", val2=v2))
                in_use.clear()
                preferred_reg = None
                last_holder = f"T{dest_reg}"

        footer = f"{main_class_id} PMAIN -> {last_holder}" if last_holder else ""
        return salida, footer

    def _alloc_reg(
        self,
        in_use: Set[int],
        preferred_reg: Optional[int] = None,
    ) -> int:
        free = {1, 2, 3} - in_use
        if free:
            reg = preferred_reg if (preferred_reg is not None and preferred_reg in free) else min(free)
            in_use.add(reg)
            return reg

        raise ValueError(
            "Límite de registros excedido: la expresión requiere más de 3 registros simultáneos (1 <= n <= 3)."
        )

    def _literal_or_id_to_typed(self, tok: str, env: Dict[str, TypedVal]) -> TypedVal:
        if tok in env:
            return env[tok]
        if tok.startswith('"') and tok.endswith('"'):
            return TypedVal(tok[1:-1], "String")
        if tok.startswith("'") and tok.endswith("'"):
            inner = tok[1:-1]
            ch = "\0" if inner == "\\0" else (inner[0] if inner else "\0")
            return TypedVal(ord(ch), "char")
        if tok.lower().endswith("f") and re.match(r"^-?\d+(?:\.\d+)?[fF]$", tok):
            return TypedVal(float(tok[:-1]), "float")
        if "." in tok:
            return TypedVal(float(tok), "double")
        if re.match(r"^-?\d+$", tok):
            return TypedVal(int(tok), "int")
        if tok == "random()":
            return TypedVal(0.5, "double")
        return TypedVal(0, "int")

    def _coerce_to_target(self, tv: TypedVal, target_type: str) -> TypedVal:
        if target_type == "float":
            val = tv.raw_val if isinstance(tv.raw_val, (int, float)) else 0.0
            return TypedVal(float(val), "float")
        if target_type == "double":
            val = tv.raw_val if isinstance(tv.raw_val, (int, float)) else 0.0
            return TypedVal(float(val), "double")
        if target_type == "int":
            val = tv.raw_val if isinstance(tv.raw_val, (int, float)) else 0
            return TypedVal(int(val), "int")
        if target_type == "char":
            val = int(tv.raw_val) if isinstance(tv.raw_val, (int, float)) else 0
            return TypedVal(val, "char")
        if target_type == "String":
            return TypedVal(str(tv.raw_val), "String")
        return tv

    def _eval_binary_typed(self, v1: TypedVal, ope: str, v2: TypedVal) -> TypedVal:
        if ope == ".":
            if str(v2.raw_val) == "length()" or v2.vtype == "int":
                s_len = len(str(v1.raw_val))
                return TypedVal(s_len, "int")
            return TypedVal(0.5, "double")

        if ope == "+" and (v1.vtype == "String" or v2.vtype == "String"):
            left_s = v1.format_res().strip('"') if v1.vtype != "String" else str(v1.raw_val)
            right_s = v2.format_res().strip('"') if v2.vtype != "String" else str(v2.raw_val)
            return TypedVal(f"{left_s}{right_s}", "String")

        a = float(v1.raw_val) if isinstance(v1.raw_val, (int, float)) else 0.0
        b = float(v2.raw_val) if isinstance(v2.raw_val, (int, float)) else 0.0

        if "double" in (v1.vtype, v2.vtype):
            res_type = "double"
        elif "float" in (v1.vtype, v2.vtype):
            res_type = "float"
        else:
            res_type = "int"

        if ope == "+":
            res = a + b
        elif ope == "-":
            res = a - b
        elif ope == "*":
            res = a * b
        elif ope == "/":
            res = 0 if b == 0 else (a / b)
        elif ope == "%":
            res = 0 if b == 0 else (a % b)
        else:
            res = 0

        if res_type == "int":
            return TypedVal(int(res), "int")
        return TypedVal(float(res), res_type)