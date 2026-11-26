import re
from typing import Dict, List, Optional, Tuple
from backend.entities.intermediate_code import Cuadruplo, Triplo
from backend.entities.optimization_row import OptimizationRow


class OptimizerEngine:
    """
    Aplica optimizaciones locales y derivadas de la Unidad 3 (U3 OPTIMIZACIÓN GB):
      - FO / FOD : Folding
      - PC / PCD : Propagación de Constantes (incluyendo literales char como '@' -> 64)
      - SE / SED : Simplificación de Expresiones
      - RS / RSD : Reducción de Subexpresiones Comunes
      - CM / CMD : Código Muerto
    """

    NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?[fF]?$")
    CHAR_RE = re.compile(r"^'(?:\\.|[^'])'$")

    def optimize_cuadruplos(self, cuadruplos: List[Cuadruplo]) -> List[OptimizationRow]:
        if not cuadruplos:
            return []

        ops = [
            {
                "orig_idx": c.indice,
                "orig_str": str(c),
                "val1": c.val1,
                "ope": c.ope,
                "val2": c.val2,
                "res": c.res,
                "acronym": "-",
                "affected": set(),
                "eliminated": False,
                "modified_by_cascade": False,
            }
            for c in cuadruplos
        ]

        self._run_optimization_passes(ops)
        return self._build_rows(ops, is_triplo=False)

    def optimize_triplos(self, triplos: List[Triplo]) -> List[OptimizationRow]:
        if not triplos:
            return []

        ops = [
            {
                "orig_idx": t.indice,
                "orig_str": str(t),
                "val1": t.val1,
                "ope": t.ope,
                "val2": t.val2,
                "res": "",
                "acronym": "-",
                "affected": set(),
                "eliminated": False,
                "modified_by_cascade": False,
            }
            for t in triplos
        ]

        self._run_optimization_passes(ops)
        return self._build_rows(ops, is_triplo=True)

    def _run_optimization_passes(self, ops: List[dict]) -> None:
        assign_counts: Dict[str, int] = {}
        for inst in ops:
            if inst["ope"] == "=":
                assign_counts[inst["val1"]] = assign_counts.get(inst["val1"], 0) + 1

        changed = True
        pass_num = 0
        while changed:
            changed = False
            pass_num += 1
            is_derived = pass_num > 1

            const_map: Dict[str, Tuple[str, int]] = {}
            alias_map: Dict[str, Tuple[str, int]] = {}
            expr_map: Dict[Tuple[str, str, str], Tuple[str, int]] = {}

            for i, inst in enumerate(ops):
                if inst["eliminated"]:
                    continue

                v1, ope, v2 = inst["val1"], inst["ope"], inst["val2"]
                ref_token = f"[{inst['orig_idx']}]"
                propagated_here = False

                if ope != "=" and v1 in alias_map:
                    new_v1, src_i = alias_map[v1]
                    inst["val1"] = new_v1
                    v1 = new_v1
                    ops[src_i]["affected"].add(str(inst["orig_idx"]))
                    inst["modified_by_cascade"] = True
                    changed = True

                if v2 in alias_map:
                    new_v2, src_i = alias_map[v2]
                    inst["val2"] = new_v2
                    v2 = new_v2
                    ops[src_i]["affected"].add(str(inst["orig_idx"]))
                    inst["modified_by_cascade"] = True
                    changed = True

                # 1. Propagación de Constantes (PC / PCD)
                if ope != "=" and v1 in const_map:
                    c_val, src_i = const_map[v1]
                    inst["val1"] = c_val
                    v1 = c_val
                    ops[src_i]["affected"].add(str(inst["orig_idx"]))
                    if ops[src_i]["acronym"] == "-":
                        ops[src_i]["acronym"] = "PCD" if ops[src_i]["modified_by_cascade"] else "PC"
                    ops[src_i]["eliminated"] = True
                    inst["modified_by_cascade"] = True
                    propagated_here = True
                    changed = True

                if v2 in const_map:
                    c_val, src_i = const_map[v2]
                    inst["val2"] = c_val
                    v2 = c_val
                    ops[src_i]["affected"].add(str(inst["orig_idx"]))
                    if ops[src_i]["acronym"] == "-":
                        ops[src_i]["acronym"] = "PCD" if ops[src_i]["modified_by_cascade"] else "PC"
                    ops[src_i]["eliminated"] = True
                    inst["modified_by_cascade"] = True
                    propagated_here = True
                    changed = True

                # 2. Folding (FO / FOD)
                if ope in ("+", "-", "*", "/", "%") and self._is_number(v1) and self._is_number(v2):
                    folded = self._eval_constant(v1, ope, v2)
                    if folded is not None:
                        tag = "FOD" if (is_derived or inst["modified_by_cascade"] or propagated_here) else "FO"
                        inst["acronym"] = tag
                        inst["eliminated"] = True
                        const_map[ref_token] = (folded, i)
                        changed = True
                        continue

                # 3. Simplificación de Expresiones (SE / SED)
                if ope in ("+", "-", "*", "/"):
                    simp = self._simplify_expression(v1, ope, v2)
                    if simp is not None:
                        kind, simp_val = simp
                        tag = "SED" if (is_derived or inst["modified_by_cascade"] or propagated_here) else "SE"
                        inst["acronym"] = tag
                        inst["eliminated"] = True
                        if kind == "ZERO":
                            const_map[ref_token] = ("0", i)
                        else:
                            alias_map[ref_token] = (simp_val, i)
                        changed = True
                        continue

                # 4. Reducción de Subexpresiones Comunes (RS / RSD)
                if ope in ("+", "-", "*", "/", "%"):
                    key = (v1, ope, v2) if ope not in ("+", "*") else tuple(sorted([v1, v2])) + (ope,)
                    if key in expr_map:
                        prev_ref, prev_i = expr_map[key]
                        if not ops[prev_i]["eliminated"]:
                            tag = "RSD" if (is_derived or inst["modified_by_cascade"]) else "RS"
                            inst["acronym"] = tag
                            inst["eliminated"] = True
                            alias_map[ref_token] = (prev_ref, i)
                            changed = True
                            continue
                    else:
                        expr_map[key] = (ref_token, i)

                # Registrar constante asignada a IDx y a su referencia [k] (numérica o carácter como '@')
                if ope == "=" and assign_counts.get(v1, 0) == 1:
                    const_val = self._extract_constant_value(v2, inst["res"])
                    if const_val is not None:
                        const_map[v1] = (const_val, i)
                        const_map[ref_token] = (const_val, i)

        # 5. Código Muerto (CM / CMD)
        dead_pass = True
        while dead_pass:
            dead_pass = False
            used_refs = set()
            for inst in ops:
                if inst["eliminated"]:
                    continue
                if inst["ope"] == "=":
                    used_refs.add(inst["val2"])
                else:
                    used_refs.add(inst["val1"])
                    used_refs.add(inst["val2"])

            for inst in ops:
                if inst["eliminated"]:
                    continue
                ref_token = f"[{inst['orig_idx']}]"
                if inst["ope"] == "=" and inst["val1"] not in used_refs and ref_token not in used_refs:
                    inst["acronym"] = "CMD" if inst["modified_by_cascade"] else "CM"
                    inst["eliminated"] = True
                    dead_pass = True

    def _build_rows(self, ops: List[dict], is_triplo: bool) -> List[OptimizationRow]:
        rows: List[OptimizationRow] = []
        new_idx = 1

        for inst in ops:
            afectados = str(min(int(x) for x in inst["affected"])) if inst["affected"] else "-"

            if inst["eliminated"]:
                if inst["modified_by_cascade"]:
                    if is_triplo:
                        preview = f"{new_idx}. ({inst['val1']}, {inst['ope']}, {inst['val2']}) -> ELIMINAR"
                    else:
                        preview = f"{new_idx}. ({inst['val1']}, {inst['ope']}, {inst['val2']}, {inst['res']}) -> ELIMINAR"
                else:
                    preview = "ELIMINAR"

                rows.append(
                    OptimizationRow(
                        cuadruplo_original=inst["orig_str"],
                        acronimo_optimizacion=inst["acronym"],
                        cuadruplo_afectado=afectados,
                        cuadruplo_modificado=preview,
                    )
                )
            else:
                if is_triplo:
                    new_str = f"{new_idx}. ({inst['val1']}, {inst['ope']}, {inst['val2']})"
                else:
                    new_str = f"{new_idx}. ({inst['val1']}, {inst['ope']}, {inst['val2']}, {inst['res']})"

                mod_text = new_str if (inst["modified_by_cascade"] or new_idx != inst["orig_idx"]) else "-"
                rows.append(
                    OptimizationRow(
                        cuadruplo_original=inst["orig_str"],
                        acronimo_optimizacion=inst["acronym"],
                        cuadruplo_afectado=afectados,
                        cuadruplo_modificado=mod_text,
                    )
                )
                new_idx += 1

        return rows

    def _strip_f(self, tok: str) -> str:
        return tok[:-1] if tok.lower().endswith("f") else tok

    def _is_number(self, token: str) -> bool:
        return bool(self.NUMBER_RE.match(token.strip()))

    def _extract_constant_value(self, val2: str, res_col: str) -> Optional[str]:
        tok = val2.strip()
        if self._is_number(tok):
            return self._strip_f(tok)
        if self.CHAR_RE.match(tok):
            if res_col and self._is_number(res_col):
                return self._strip_f(res_col)
            inner = tok[1:-1]
            ch = "\0" if inner == "\\0" else inner[0]
            return str(ord(ch))
        return None

    def _eval_constant(self, v1: str, ope: str, v2: str) -> Optional[str]:
        try:
            a = float(self._strip_f(v1))
            b = float(self._strip_f(v2))
            if ope == "+":
                res = a + b
            elif ope == "-":
                res = a - b
            elif ope == "*":
                res = a * b
            elif ope == "/":
                if b == 0:
                    return None
                res = a / b
            elif ope == "%":
                if b == 0:
                    return None
                res = a % b
            else:
                return None

            if res.is_integer():
                return str(int(res))
            return f"{res:.6f}".rstrip("0").rstrip(".")
        except ValueError:
            return None

    def _simplify_expression(self, v1: str, ope: str, v2: str) -> Optional[Tuple[str, str]]:
        n1 = self._strip_f(v1)
        n2 = self._strip_f(v2)
        if ope == "+":
            if n2 in ("0", "0.0"):
                return ("IDENTITY", v1)
            if n1 in ("0", "0.0"):
                return ("IDENTITY", v2)
        elif ope == "-":
            if n2 in ("0", "0.0"):
                return ("IDENTITY", v1)
            if v1 == v2:
                return ("ZERO", "0")
        elif ope == "*":
            if n2 in ("1", "1.0"):
                return ("IDENTITY", v1)
            if n1 in ("1", "1.0"):
                return ("IDENTITY", v2)
            if n1 in ("0", "0.0") or n2 in ("0", "0.0"):
                return ("ZERO", "0")
        elif ope == "/":
            if n2 in ("1", "1.0"):
                return ("IDENTITY", v1)
            if n1 in ("0", "0.0") and n2 not in ("0", "0.0"):
                return ("ZERO", "0")
        return None