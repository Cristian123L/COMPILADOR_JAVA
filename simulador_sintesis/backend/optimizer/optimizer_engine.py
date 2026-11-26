import re
from typing import Dict, List, Optional, Tuple
from backend.entities.intermediate_code import Cuadruplo, Triplo
from backend.entities.optimization_row import OptimizationRow


class OptimizerEngine:
    """
    Aplica las optimizaciones locales de la Unidad 3 (Mtra. Nancy Carolina Quintana):
      - FO  / FOD : Folding (operaciones entre constantes)
      - PC  / PCD : Propagación de Constantes
      - SE  / SED : Simplificación de Expresiones (+0, -0, *1, /1, *0, etc.)
      - RS  / RSD : Reducción de Subexpresiones Comunes
      - CM  / CMD : Código Muerto (variables/registros no utilizados)
    """

    NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

    def optimize_cuadruplos(self, cuadruplos: List[Cuadruplo]) -> Tuple[List[OptimizationRow], List[Cuadruplo]]:
        if not cuadruplos:
            return [], []

        # Clonar instrucciones en una representación mutable interna
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
                "reason_detail": "",
            }
            for c in cuadruplos
        ]

        # Pasadas iterativas hasta alcanzar punto fijo (permite detectar derivadas con 'D')
        changed = True
        pass_num = 0
        while changed:
            changed = False
            pass_num += 1
            is_derived = pass_num > 1

            const_map: Dict[str, str] = {}          # var/temp -> literal constante
            const_origin: Dict[str, int] = {}        # var/temp -> índice original que la definió
            expr_map: Dict[Tuple[str, str, str], Tuple[str, int]] = {}  # (v1, op, v2) -> (res, orig_idx)

            for i, inst in enumerate(ops):
                if inst["eliminated"]:
                    continue

                v1, ope, v2, res = inst["val1"], inst["ope"], inst["val2"], inst["res"]

                # 1. Propagación de Constantes (PC / PCD) hacia los operandos de esta fila
                propagated_here = False
                if v1 in const_map:
                    origin_i = const_origin[v1]
                    inst["val1"] = const_map[v1]
                    v1 = inst["val1"]
                    ops[origin_i]["affected"].add(str(inst["orig_idx"]))
                    if ops[origin_i]["acronym"] == "-":
                        ops[origin_i]["acronym"] = "PCD" if ops[origin_i]["modified_by_cascade"] else "PC"
                    ops[origin_i]["eliminated"] = True
                    inst["modified_by_cascade"] = True
                    propagated_here = True
                    changed = True

                if ope != "=" and v2 in const_map:
                    origin_i = const_origin[v2]
                    inst["val2"] = const_map[v2]
                    v2 = inst["val2"]
                    ops[origin_i]["affected"].add(str(inst["orig_idx"]))
                    if ops[origin_i]["acronym"] == "-":
                        ops[origin_i]["acronym"] = "PCD" if ops[origin_i]["modified_by_cascade"] else "PC"
                    ops[origin_i]["eliminated"] = True
                    inst["modified_by_cascade"] = True
                    propagated_here = True
                    changed = True

                # 2. Folding (FO / FOD): ambos operandos son constantes numéricas
                if ope in ("+", "-", "*", "/", "%") and self._is_number(v1) and self._is_number(v2):
                    folded_val = self._eval_constant(v1, ope, v2)
                    if folded_val is not None:
                        tag = "FOD" if (is_derived or inst["modified_by_cascade"] or propagated_here) else "FO"
                        inst["acronym"] = tag
                        inst["eliminated"] = True
                        const_map[res] = folded_val
                        const_origin[res] = i
                        # Buscar dónde se usa 'res' para marcar afectado
                        for j in range(i + 1, len(ops)):
                            if not ops[j]["eliminated"] and res in (ops[j]["val1"], ops[j]["val2"]):
                                inst["affected"].add(str(ops[j]["orig_idx"]))
                        changed = True
                        continue

                # 3. Simplificación de Expresiones (SE / SED)
                if ope in ("+", "-", "*", "/"):
                    simp = self._simplify_expression(v1, ope, v2)
                    if simp is not None:
                        kind, simplified_val = simp
                        tag = "SED" if (is_derived or inst["modified_by_cascade"] or propagated_here) else "SE"
                        inst["acronym"] = tag
                        if kind == "ZERO":
                            inst["eliminated"] = True
                            const_map[res] = "0"
                            const_origin[res] = i
                            for j in range(i + 1, len(ops)):
                                if not ops[j]["eliminated"] and res in (ops[j]["val1"], ops[j]["val2"]):
                                    inst["affected"].add(str(ops[j]["orig_idx"]))
                        elif kind == "IDENTITY":
                            # Ej: x + 0 -> x, x * 1 -> x, x / 1 -> x
                            inst["eliminated"] = True
                            # Reemplazar el temporal 'res' por 'simplified_val' en instrucciones posteriores
                            for j in range(i + 1, len(ops)):
                                if ops[j]["eliminated"]:
                                    continue
                                if ops[j]["val1"] == res:
                                    ops[j]["val1"] = simplified_val
                                    ops[j]["modified_by_cascade"] = True
                                    inst["affected"].add(str(ops[j]["orig_idx"]))
                                if ops[j]["val2"] == res:
                                    ops[j]["val2"] = simplified_val
                                    ops[j]["modified_by_cascade"] = True
                                    inst["affected"].add(str(ops[j]["orig_idx"]))
                        changed = True
                        continue

                # 4. Reducción de Subexpresiones Comunes (RS / RSD)
                if ope in ("+", "-", "*", "/", "%"):
                    key = (v1, ope, v2) if ope not in ("+", "*") else tuple(sorted([v1, v2])) + (ope,)
                    if key in expr_map:
                        prev_res, prev_i = expr_map[key]
                        if not ops[prev_i]["eliminated"]:
                            tag = "RSD" if (is_derived or inst["modified_by_cascade"]) else "RS"
                            inst["acronym"] = tag
                            inst["eliminated"] = True
                            for j in range(i + 1, len(ops)):
                                if ops[j]["eliminated"]:
                                    continue
                                if ops[j]["val1"] == res:
                                    ops[j]["val1"] = prev_res
                                    ops[j]["modified_by_cascade"] = True
                                    inst["affected"].add(str(ops[j]["orig_idx"]))
                                if ops[j]["val2"] == res:
                                    ops[j]["val2"] = prev_res
                                    ops[j]["modified_by_cascade"] = True
                                    inst["affected"].add(str(ops[j]["orig_idx"]))
                            changed = True
                            continue
                    else:
                        expr_map[key] = (res, i)

                # Registrar constante directa para propagación (ej: base = 10)
                if ope == "=" and self._is_number(v1):
                    const_map[res] = v1
                    const_origin[res] = i
                elif ope == "=" and res in const_map:
                    # Si la variable se reasigna con algo no constante, deja de ser constante
                    del const_map[res]
                    const_origin.pop(res, None)

        # 5. Código Muerto (CM / CMD): instrucciones cuya variable destino nunca se vuelve a leer
        dead_pass = True
        while dead_pass:
            dead_pass = False
            used_symbols = set()
            for inst in ops:
                if inst["eliminated"]:
                    continue
                if inst["ope"] == "SOUT":
                    used_symbols.add(inst["val1"])
                else:
                    if inst["val1"] and inst["val1"] != "-":
                        used_symbols.add(inst["val1"])
                    if inst["val2"] and inst["val2"] != "-":
                        used_symbols.add(inst["val2"])

            for inst in ops:
                if inst["eliminated"] or inst["ope"] == "SOUT":
                    continue
                target = inst["res"]
                if target not in used_symbols:
                    inst["acronym"] = "CMD" if inst["modified_by_cascade"] else "CM"
                    inst["eliminated"] = True
                    dead_pass = True

        # Construir filas de la tabla de optimización (Inciso 4)
        rows: List[OptimizationRow] = []
        optimized_cuadruplos: List[Cuadruplo] = []
        new_idx = 1

        for inst in ops:
            afectados = ", ".join(sorted(inst["affected"], key=lambda x: int(x))) if inst["affected"] else "-"

            if inst["eliminated"]:
                # Mostrar cómo quedó antes de eliminarse si tuvo cambio previo, seguido de ELIMINAR
                if inst["modified_by_cascade"]:
                    prev_text = f"{new_idx}. ({inst['val1']}, {inst['ope']}, {inst['val2']}, {inst['res']}) -> ELIMINAR"
                else:
                    prev_text = "ELIMINAR"
                rows.append(
                    OptimizationRow(
                        cuadruplo_original=inst["orig_str"],
                        acronimo_optimizacion=inst["acronym"],
                        cuadruplo_afectado=afectados,
                        cuadruplo_modificado=prev_text,
                    )
                )
            else:
                new_c = Cuadruplo(
                    indice=new_idx,
                    val1=inst["val1"],
                    ope=inst["ope"],
                    val2=inst["val2"],
                    res=inst["res"],
                )
                optimized_cuadruplos.append(new_c)
                mod_text = str(new_c) if (inst["modified_by_cascade"] or new_idx != inst["orig_idx"]) else "-"
                rows.append(
                    OptimizationRow(
                        cuadruplo_original=inst["orig_str"],
                        acronimo_optimizacion=inst["acronym"],
                        cuadruplo_afectado=afectados,
                        cuadruplo_modificado=mod_text,
                    )
                )
                new_idx += 1

        return rows, optimized_cuadruplos

    def optimize_triplos(self, triplos: List[Triplo], cuadruplos_equiv: List[Cuadruplo]) -> List[OptimizationRow]:
        """
        Optimiza Triplos reutilizando el análisis de flujo de datos y mapeando
        cada fila al formato n(val1, ope, val2).
        """
        cuad_rows, _ = self.optimize_cuadruplos(cuadruplos_equiv)
        rows: List[OptimizationRow] = []

        for idx, t in enumerate(triplos):
            if idx < len(cuad_rows):
                cr = cuad_rows[idx]
                mod = cr.cuadruplo_modificado
                if mod not in ("-", "ELIMINAR") and "-> ELIMINAR" not in mod:
                    # Convertir el cuádruplo reescrito a formato triplo n(v1, op, v2)
                    mod = self._cuadruplo_str_to_triplo_str(mod, t)
                rows.append(
                    OptimizationRow(
                        cuadruplo_original=str(t),
                        acronimo_optimizacion=cr.acronimo_optimizacion,
                        cuadruplo_afectado=cr.cuadruplo_afectado,
                        cuadruplo_modificado=mod,
                    )
                )
            else:
                rows.append(
                    OptimizationRow(
                        cuadruplo_original=str(t),
                        acronimo_optimizacion="-",
                        cuadruplo_afectado="-",
                        cuadruplo_modificado="-",
                    )
                )
        return rows

    def _cuadruplo_str_to_triplo_str(self, cuad_str: str, orig_triplo: Triplo) -> str:
        m = re.match(r"^(\d+)\.\s*\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)$", cuad_str.strip())
        if not m:
            return str(orig_triplo)
        n, v1, ope, v2, res = m.groups()
        if ope == "=":
            return f"{n}({res}, =, {v1})"
        if ope == "SOUT":
            return f"{n}(SOUT, print, {v1})"
        return f"{n}({v1}, {ope}, {v2})"

    def _is_number(self, token: str) -> bool:
        return bool(self.NUMBER_RE.match(token.strip()))

    def _eval_constant(self, v1: str, ope: str, v2: str) -> Optional[str]:
        try:
            a = float(v1)
            b = float(v2)
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
            return f"{res:.4f}".rstrip("0").rstrip(".")
        except ValueError:
            return None

    def _simplify_expression(self, v1: str, ope: str, v2: str) -> Optional[Tuple[str, str]]:
        # Operaciones neutras / simplificables (Diapositiva 12)
        if ope == "+":
            if v2 == "0":
                return ("IDENTITY", v1)
            if v1 == "0":
                return ("IDENTITY", v2)
        elif ope == "-":
            if v2 == "0":
                return ("IDENTITY", v1)
            if v1 == v2:
                return ("ZERO", "0")
        elif ope == "*":
            if v2 == "1":
                return ("IDENTITY", v1)
            if v1 == "1":
                return ("IDENTITY", v2)
            if v1 == "0" or v2 == "0":
                return ("ZERO", "0")
        elif ope == "/":
            if v2 == "1":
                return ("IDENTITY", v1)
            if v1 == "0" and v2 != "0":
                return ("ZERO", "0")
        return None