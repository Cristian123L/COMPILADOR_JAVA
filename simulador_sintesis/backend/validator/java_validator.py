import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from backend.entities.symbol_entry import SymbolEntry
from backend.entities.validation_result import ValidationResult


@dataclass
class IRInstruction:
    """Instrucción intermedia normalizada con IDs resueltos por ámbito."""
    kind: str                  # ASSIGN, NEW_OBJ, SOUT, RTN, CALL, CALL_SOUT
    target_id: str             # Ej. ID2, PMAIN, ID4
    target_type: str           # int, float, double, char, String, boolean, void, o clase
    expr: str                  # Expresión con nombres originales reescritos a IDx
    scope: str                 # Global o nombre del método
    method_owner_id: str = ""  # ID del método si pertenece a un método auxiliar


@dataclass
class ExtendedValidationResult(ValidationResult):
    symbols: List[SymbolEntry] = field(default_factory=list)
    instructions: List[IRInstruction] = field(default_factory=list)
    main_class_id: str = "ID1"
    error_line: Optional[int] = None


class JavaValidator:
    """
    Valida sintaxis y compatibilidad de tipos en Java para la Etapa de Síntesis,
    construyendo la Tabla de Símbolos (ID1, ID2...) por ámbito Global y Local.
    """

    VALID_TYPES = {"int", "double", "float", "long", "short", "byte", "boolean", "char", "String"}
    RETURN_TYPES = VALID_TYPES | {"void"}
    NUMERIC_TYPES = {"double", "float", "long", "int", "short", "byte", "char"}
    RESERVED = VALID_TYPES | {
        "public", "private", "protected", "static", "final", "class", "void",
        "new", "return", "if", "else", "while", "for", "System", "out",
        "println", "print", "Math", "random", "length", "charAt", "true", "false", "null"
    }

    DEFAULT_VALUES = {
        "int": "0",
        "long": "0",
        "short": "0",
        "byte": "0",
        "float": "0.0f",
        "double": "0.0",
        "char": "'\\0'",
        "boolean": "false",
        "String": '""',
    }

    def validate(self, source_code: str) -> ExtendedValidationResult:
        if not source_code or not source_code.strip():
            return ExtendedValidationResult(
                is_valid=False,
                errors=["El editor de código está vacío."],
                error_line=1,
            )

        clean_code = self._strip_comments_preserve_lines(source_code)

        unclosed_line = self._find_unclosed_quotes(clean_code)
        if unclosed_line is not None:
            return ExtendedValidationResult(
                is_valid=False,
                errors=[f"Error léxico en línea {unclosed_line}: literal de cadena o carácter sin cerrar."],
                error_line=unclosed_line,
            )

        illegal_line = self._find_illegal_chars(clean_code)
        if illegal_line is not None:
            return ExtendedValidationResult(
                is_valid=False,
                errors=[f"Error léxico en línea {illegal_line}: símbolo no reconocido por el lenguaje Java."],
                error_line=illegal_line,
            )

        if clean_code.count("{") != clean_code.count("}"):
            return ExtendedValidationResult(
                is_valid=False,
                errors=["Error sintáctico: llaves '{' y '}' desbalanceadas."],
                error_line=self._find_unbalanced_line(clean_code, "{", "}"),
            )
        if clean_code.count("(") != clean_code.count(")"):
            return ExtendedValidationResult(
                is_valid=False,
                errors=["Error sintáctico: paréntesis '(' y ')' desbalanceados."],
                error_line=self._find_unbalanced_line(clean_code, "(", ")"),
            )

        class_match = re.search(r"\bpublic\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", clean_code)
        if not class_match:
            return ExtendedValidationResult(
                is_valid=False,
                errors=["Error sintáctico (regla CLASE): falta 'public class NombreClase {'."],
                error_line=1,
            )

        class_name = class_match.group(1)
        class_open = class_match.end() - 1
        class_close = self._find_matching_brace(clean_code, class_open)
        if class_close is None:
            return ExtendedValidationResult(
                is_valid=False,
                errors=["Error sintáctico: no se encontró llave de cierre '}' de la clase principal."],
                error_line=clean_code[:class_open].count("\n") + 1,
            )

        before_class = clean_code[:class_match.start()].strip()
        for raw_l in before_class.splitlines():
            s = raw_l.rstrip(";").strip()
            if not s:
                continue
            if not (re.match(r"^package\s+[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$", s) or
                    re.match(r"^import\s+[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?:\.\*)?$", s)):
                err_l = self._line_of_snippet(clean_code, raw_l.strip())
                return ExtendedValidationResult(
                    is_valid=False,
                    errors=[f"Error sintáctico en línea {err_l}: sentencia inválida fuera de la clase ('{raw_l.strip()}')."],
                    error_line=err_l,
                )

        main_pattern = re.compile(
            r"\bpublic\s+static\s+void\s+main\s*\(\s*String\s*(?:\[\s*\]\s*([A-Za-z_]\w*)|([A-Za-z_]\w*)\s*\[\s*\])\s*\)\s*\{"
        )
        main_match = main_pattern.search(clean_code, class_open, class_close)
        if not main_match:
            return ExtendedValidationResult(
                is_valid=False,
                class_name=class_name,
                errors=["Error sintáctico (regla MAIN): falta el método 'public static void main(String[] args)'."],
                error_line=clean_code[:class_open].count("\n") + 1,
            )

        symbols: List[SymbolEntry] = []
        sym_by_id: Dict[str, SymbolEntry] = {}
        id_counter = 1

        def next_id() -> str:
            nonlocal id_counter
            val = f"ID{id_counter}"
            id_counter += 1
            return val

        def register_symbol(entry: SymbolEntry) -> SymbolEntry:
            symbols.append(entry)
            sym_by_id[entry.id_code] = entry
            return entry

        main_class_id = next_id()
        register_symbol(
            SymbolEntry(
                id_code=main_class_id,
                lexeme=class_name,
                category="Clase Principal",
                data_type="class",
                scope="Global",
            )
        )

        scopes: Dict[str, Dict[str, SymbolEntry]] = {"Global": {}}
        methods_info: Dict[str, dict] = {}
        global_decls: List[Tuple[SymbolEntry, str, int]] = []

        pos = class_open + 1
        main_block_info = None

        while pos < class_close:
            while pos < class_close and (clean_code[pos].isspace() or clean_code[pos] == ";"):
                pos += 1
            if pos >= class_close:
                break

            line_num = clean_code[:pos].count("\n") + 1
            rest = clean_code[pos:class_close]

            m_main = main_pattern.match(rest)
            if m_main:
                brace_idx = pos + m_main.end() - 1
                end_brace = self._find_matching_brace(clean_code, brace_idx)
                arg_name = m_main.group(1) or m_main.group(2)
                main_block_info = (brace_idx + 1, end_brace, arg_name, line_num)
                pos = end_brace + 1
                continue

            m_method = re.match(
                r"^(?:(?:public|private|protected)\s+)?(?:static\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{",
                rest,
            )
            if m_method:
                ret_type, meth_name, params_str = m_method.groups()
                if ret_type not in self.RETURN_TYPES and ret_type != class_name:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: tipo de retorno '{ret_type}' no válido."],
                        error_line=line_num,
                    )
                if meth_name in scopes["Global"]:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: identificador '{meth_name}' duplicado."],
                        error_line=line_num,
                    )

                meth_entry = register_symbol(
                    SymbolEntry(
                        id_code=next_id(),
                        lexeme=meth_name,
                        category="Método",
                        data_type=ret_type,
                        scope="Global",
                    )
                )
                scopes["Global"][meth_name] = meth_entry
                scopes[meth_name] = {}

                param_entries: List[SymbolEntry] = []
                if params_str.strip():
                    for p in params_str.split(","):
                        pm = re.match(r"^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*$", p)
                        if not pm or (pm.group(1) not in self.VALID_TYPES and pm.group(1) != class_name):
                            return ExtendedValidationResult(
                                is_valid=False,
                                class_name=class_name,
                                errors=[f"Error sintáctico en línea {line_num}: parámetro inválido '{p.strip()}'."],
                                error_line=line_num,
                            )
                        p_type, p_name = pm.groups()
                        if p_name in scopes[meth_name]:
                            return ExtendedValidationResult(
                                is_valid=False,
                                class_name=class_name,
                                errors=[f"Error semántico en línea {line_num}: parámetro '{p_name}' duplicado."],
                                error_line=line_num,
                            )
                        p_entry = register_symbol(
                            SymbolEntry(
                                id_code=next_id(),
                                lexeme=p_name,
                                category="Parámetro",
                                data_type=p_type,
                                scope=meth_name,
                            )
                        )
                        scopes[meth_name][p_name] = p_entry
                        param_entries.append(p_entry)

                brace_idx = pos + m_method.end() - 1
                end_brace = self._find_matching_brace(clean_code, brace_idx)
                methods_info[meth_name] = {
                    "entry": meth_entry,
                    "params": param_entries,
                    "body_start": brace_idx + 1,
                    "body_end": end_brace,
                }
                pos = end_brace + 1
                continue

            semi_idx = clean_code.find(";", pos, class_close)
            if semi_idx == -1:
                snippet = rest.splitlines()[0].strip()
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error sintáctico en línea {line_num}: falta ';' en '{snippet}'."],
                    error_line=line_num,
                )

            stmt_raw = clean_code[pos:semi_idx].strip()
            m_attr = re.match(
                r"^(?:(?:public|private|protected)\s+)?(?:static\s+)?(?:final\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)(?:\s*=\s*(.+))?$",
                stmt_raw,
                re.DOTALL,
            )
            if not m_attr:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error sintáctico en línea {line_num}: declaración de atributo inválida '{stmt_raw}'."],
                    error_line=line_num,
                )

            var_type, var_name, expr = m_attr.groups()
            if var_type not in self.VALID_TYPES:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error semántico en línea {line_num}: tipo de dato desconocido '{var_type}'."],
                    error_line=line_num,
                )
            if var_name in scopes["Global"]:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error semántico en línea {line_num}: atributo '{var_name}' ya fue declarado."],
                    error_line=line_num,
                )

            init_val = expr.strip() if expr is not None else self.DEFAULT_VALUES[var_type]
            attr_entry = register_symbol(
                SymbolEntry(
                    id_code=next_id(),
                    lexeme=var_name,
                    category="Atributo Global",
                    data_type=var_type,
                    scope="Global",
                    initial_value=init_val,
                )
            )
            scopes["Global"][var_name] = attr_entry
            global_decls.append((attr_entry, init_val, line_num))
            pos = semi_idx + 1

        instructions: List[IRInstruction] = []
        cleaned_statements: List[str] = []
        emitted_methods: Set[str] = set()

        for attr_entry, init_expr, lnum in global_decls:
            resolved_expr, err = self._resolve_expression(init_expr, "Global", scopes, class_name, main_class_id)
            if err:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error en línea {lnum}: {err}"],
                    error_line=lnum,
                )
            type_err = self._check_assignment_types(attr_entry.data_type, resolved_expr, sym_by_id)
            if type_err:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error semántico en línea {lnum}: {type_err}"],
                    error_line=lnum,
                )
            instructions.append(
                IRInstruction(
                    kind="ASSIGN",
                    target_id=attr_entry.id_code,
                    target_type=attr_entry.data_type,
                    expr=resolved_expr,
                    scope="Global",
                )
            )
            cleaned_statements.append(f"{attr_entry.id_code} = {resolved_expr}")

        m_start, m_end, arg_name, main_line = main_block_info
        scopes["main"] = {}
        args_entry = register_symbol(
            SymbolEntry(
                id_code=next_id(),
                lexeme=arg_name,
                category="Parámetro",
                data_type="String[]",
                scope="main",
            )
        )
        scopes["main"][arg_name] = args_entry

        err_res = self._parse_block_statements(
            clean_code=clean_code,
            start_idx=m_start,
            end_idx=m_end,
            scope="main",
            scopes=scopes,
            register_symbol=register_symbol,
            sym_by_id=sym_by_id,
            next_id=next_id,
            instructions=instructions,
            cleaned_statements=cleaned_statements,
            class_name=class_name,
            main_class_id=main_class_id,
            methods_info=methods_info,
            method_entry=None,
            emitted_methods=emitted_methods,
        )
        if err_res is not None:
            return err_res

        for meth_name, minfo in methods_info.items():
            if meth_name not in emitted_methods:
                emitted_methods.add(meth_name)
                err_res = self._parse_block_statements(
                    clean_code=clean_code,
                    start_idx=minfo["body_start"],
                    end_idx=minfo["body_end"],
                    scope=meth_name,
                    scopes=scopes,
                    register_symbol=register_symbol,
                    sym_by_id=sym_by_id,
                    next_id=next_id,
                    instructions=instructions,
                    cleaned_statements=cleaned_statements,
                    class_name=class_name,
                    main_class_id=main_class_id,
                    methods_info=methods_info,
                    method_entry=minfo["entry"],
                    emitted_methods=emitted_methods,
                )
                if err_res is not None:
                    return err_res

        if len(instructions) == 0:
            return ExtendedValidationResult(
                is_valid=False,
                class_name=class_name,
                errors=[f"Error en línea {main_line}: el método main no contiene sentencias ejecutables."],
                error_line=main_line,
            )

        return ExtendedValidationResult(
            is_valid=True,
            class_name=class_name,
            errors=[],
            cleaned_statements=cleaned_statements,
            symbols=symbols,
            instructions=instructions,
            main_class_id=main_class_id,
        )

    def _parse_block_statements(
        self,
        clean_code: str,
        start_idx: int,
        end_idx: int,
        scope: str,
        scopes: Dict[str, Dict[str, SymbolEntry]],
        register_symbol,
        sym_by_id: Dict[str, SymbolEntry],
        next_id,
        instructions: List[IRInstruction],
        cleaned_statements: List[str],
        class_name: str,
        main_class_id: str,
        methods_info: Dict[str, dict],
        method_entry: Optional[SymbolEntry],
        emitted_methods: Set[str],
    ) -> Optional[ExtendedValidationResult]:
        block_text = clean_code[start_idx:end_idx]
        lines = block_text.splitlines()
        base_line = clean_code[:start_idx].count("\n") + 1

        for offset, raw_line in enumerate(lines):
            stmt_line = raw_line.strip()
            line_num = base_line + offset
            if not stmt_line or set(stmt_line) == {";"}:
                continue

            if not stmt_line.endswith(";"):
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error sintáctico en línea {line_num}: falta ';' al final de '{stmt_line}'."],
                    error_line=line_num,
                )

            stmt = stmt_line.rstrip(";").strip()
            if not stmt:
                continue

            # 1. System.out.println(...) / System.out.print(...)
            m_sout = re.match(r"^System\.out\.print(?:ln)?\s*\((.+)\)$", stmt)
            if m_sout:
                inner = m_sout.group(1).strip()
                m_obj_call = re.match(
                    rf"^new\s+{re.escape(class_name)}\s*\(\s*\)\s*\.\s*([A-Za-z_]\w*)\s*\((.*)\)$",
                    inner,
                )
                if m_obj_call:
                    called_meth, raw_args = m_obj_call.groups()
                    if called_meth not in methods_info:
                        return ExtendedValidationResult(
                            is_valid=False,
                            class_name=class_name,
                            errors=[f"Error semántico en línea {line_num}: método '{called_meth}' no existe en '{class_name}'."],
                            error_line=line_num,
                        )
                    err = self._invoke_method(
                        called_meth, raw_args, clean_code, scope, scopes, register_symbol, sym_by_id,
                        next_id, methods_info, instructions, cleaned_statements, class_name, main_class_id,
                        line_num, emitted_methods
                    )
                    if err:
                        return err
                    m_sym = methods_info[called_meth]["entry"]
                    instructions.append(
                        IRInstruction(
                            kind="CALL_SOUT",
                            target_id=main_class_id,
                            target_type=m_sym.data_type,
                            expr=m_sym.id_code,
                            scope=scope,
                        )
                    )
                    cleaned_statements.append(f"SOUT {main_class_id}.{m_sym.id_code}")
                    continue

                m_inst_call = re.match(r"^([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\((.*)\)$", inner)
                if m_inst_call and m_inst_call.group(2) in methods_info:
                    obj_name, called_meth, raw_args = m_inst_call.groups()
                    obj_sym = self._lookup_symbol(obj_name, scope, scopes)
                    if obj_sym is None or obj_sym.data_type != class_name:
                        return ExtendedValidationResult(
                            is_valid=False,
                            class_name=class_name,
                            errors=[f"Error semántico en línea {line_num}: objeto '{obj_name}' no válido."],
                            error_line=line_num,
                        )
                    err = self._invoke_method(
                        called_meth, raw_args, clean_code, scope, scopes, register_symbol, sym_by_id,
                        next_id, methods_info, instructions, cleaned_statements, class_name, main_class_id,
                        line_num, emitted_methods
                    )
                    if err:
                        return err
                    m_sym = methods_info[called_meth]["entry"]
                    instructions.append(
                        IRInstruction(
                            kind="CALL_SOUT",
                            target_id=obj_sym.id_code,
                            target_type=m_sym.data_type,
                            expr=m_sym.id_code,
                            scope=scope,
                        )
                    )
                    cleaned_statements.append(f"SOUT {obj_sym.id_code}.{m_sym.id_code}")
                    continue

                m_obj_attr = re.match(
                    rf"^new\s+{re.escape(class_name)}\s*\(\s*\)\s*\.\s*([A-Za-z_]\w*)$",
                    inner,
                )
                if m_obj_attr:
                    attr_name = m_obj_attr.group(1)
                    if attr_name not in scopes["Global"]:
                        return ExtendedValidationResult(
                            is_valid=False,
                            class_name=class_name,
                            errors=[f"Error semántico en línea {line_num}: atributo '{attr_name}' no declarado."],
                            error_line=line_num,
                        )
                    a_sym = scopes["Global"][attr_name]
                    instructions.append(
                        IRInstruction(
                            kind="CALL_SOUT",
                            target_id=main_class_id,
                            target_type=a_sym.data_type,
                            expr=a_sym.id_code,
                            scope=scope,
                        )
                    )
                    cleaned_statements.append(f"SOUT {main_class_id}.{a_sym.id_code}")
                    continue

                resolved_expr, err = self._resolve_expression(inner, scope, scopes, class_name, main_class_id)
                if err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error en línea {line_num}: {err}"],
                        error_line=line_num,
                    )
                target = method_entry.id_code if method_entry else "PMAIN"
                instructions.append(
                    IRInstruction(
                        kind="SOUT",
                        target_id=target,
                        target_type="void",
                        expr=resolved_expr,
                        scope=scope,
                        method_owner_id=method_entry.id_code if method_entry else "",
                    )
                )
                cleaned_statements.append(f"PRINT {resolved_expr}")
                continue

            # 2. Llamada directa a método: new Clase().metodo(args...);
            m_direct_call = re.match(
                rf"^new\s+{re.escape(class_name)}\s*\(\s*\)\s*\.\s*([A-Za-z_]\w*)\s*\((.*)\)$",
                stmt,
            )
            if m_direct_call:
                called_meth, raw_args = m_direct_call.groups()
                if called_meth not in methods_info:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: método '{called_meth}' no existe."],
                        error_line=line_num,
                    )
                err = self._invoke_method(
                    called_meth, raw_args, clean_code, scope, scopes, register_symbol, sym_by_id,
                    next_id, methods_info, instructions, cleaned_statements, class_name, main_class_id,
                    line_num, emitted_methods
                )
                if err:
                    return err
                m_sym = methods_info[called_meth]["entry"]
                instructions.append(
                    IRInstruction(
                        kind="CALL",
                        target_id=main_class_id,
                        target_type=m_sym.data_type,
                        expr=m_sym.id_code,
                        scope=scope,
                    )
                )
                cleaned_statements.append(f"{main_class_id}.{m_sym.id_code}")
                continue

            # 3. Sentencia return expr;
            m_ret = re.match(r"^return\s+(.+)$", stmt)
            if m_ret:
                if method_entry is None:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: 'return' con valor no permitido en main."],
                        error_line=line_num,
                    )
                resolved_expr, err = self._resolve_expression(m_ret.group(1), scope, scopes, class_name, main_class_id)
                if err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error en línea {line_num}: {err}"],
                        error_line=line_num,
                    )
                type_err = self._check_assignment_types(method_entry.data_type, resolved_expr, sym_by_id)
                if type_err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: {type_err}"],
                        error_line=line_num,
                    )
                instructions.append(
                    IRInstruction(
                        kind="RTN",
                        target_id=method_entry.id_code,
                        target_type=method_entry.data_type,
                        expr=resolved_expr,
                        scope=scope,
                        method_owner_id=method_entry.id_code,
                    )
                )
                cleaned_statements.append(f"RETURN {resolved_expr}")
                continue

            # 4. Declaración local: tipo nombre [= expr];
            m_decl = re.match(r"^(?:final\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)(?:\s*=\s*(.+))?$", stmt)
            if m_decl:
                var_type, var_name, expr = m_decl.groups()
                if var_type not in self.VALID_TYPES and var_type != class_name:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: tipo de dato no válido '{var_type}'."],
                        error_line=line_num,
                    )
                if var_name in scopes[scope]:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: variable local '{var_name}' duplicada en '{scope}'."],
                        error_line=line_num,
                    )

                if var_type == class_name:
                    init_raw = expr.strip() if expr is not None else "null"
                    if expr is not None and not re.match(rf"^new\s+{re.escape(class_name)}\s*\(\s*\)$", init_raw):
                        return ExtendedValidationResult(
                            is_valid=False,
                            class_name=class_name,
                            errors=[f"Error semántico en línea {line_num}: inicialización inválida '{init_raw}' para '{class_name}'."],
                            error_line=line_num,
                        )
                    obj_entry = register_symbol(
                        SymbolEntry(
                            id_code=next_id(),
                            lexeme=var_name,
                            category="Objeto Local",
                            data_type=class_name,
                            scope=scope,
                            initial_value=init_raw,
                        )
                    )
                    scopes[scope][var_name] = obj_entry
                    instructions.append(
                        IRInstruction(
                            kind="NEW_OBJ",
                            target_id=obj_entry.id_code,
                            target_type=class_name,
                            expr=f"new {main_class_id}",
                            scope=scope,
                        )
                    )
                    cleaned_statements.append(f"{obj_entry.id_code} = new {main_class_id}")
                    continue

                init_val = expr.strip() if expr is not None else self.DEFAULT_VALUES[var_type]
                resolved_expr, err = self._resolve_expression(init_val, scope, scopes, class_name, main_class_id)
                if err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error en línea {line_num}: {err}"],
                        error_line=line_num,
                    )
                type_err = self._check_assignment_types(var_type, resolved_expr, sym_by_id)
                if type_err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: {type_err}"],
                        error_line=line_num,
                    )

                local_entry = register_symbol(
                    SymbolEntry(
                        id_code=next_id(),
                        lexeme=var_name,
                        category="Variable Local",
                        data_type=var_type,
                        scope=scope,
                        initial_value=init_val,
                    )
                )
                scopes[scope][var_name] = local_entry
                instructions.append(
                    IRInstruction(
                        kind="ASSIGN",
                        target_id=local_entry.id_code,
                        target_type=local_entry.data_type,
                        expr=resolved_expr,
                        scope=scope,
                    )
                )
                cleaned_statements.append(f"{local_entry.id_code} = {resolved_expr}")
                continue

            # 5. Asignación a variable existente: nombre = expr;
            m_assign = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", stmt)
            if m_assign:
                var_name, expr = m_assign.groups()
                sym = self._lookup_symbol(var_name, scope, scopes)
                if sym is None:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: variable '{var_name}' no declarada antes de su uso."],
                        error_line=line_num,
                    )
                resolved_expr, err = self._resolve_expression(expr, scope, scopes, class_name, main_class_id)
                if err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error en línea {line_num}: {err}"],
                        error_line=line_num,
                    )
                type_err = self._check_assignment_types(sym.data_type, resolved_expr, sym_by_id)
                if type_err:
                    return ExtendedValidationResult(
                        is_valid=False,
                        class_name=class_name,
                        errors=[f"Error semántico en línea {line_num}: {type_err}"],
                        error_line=line_num,
                    )
                instructions.append(
                    IRInstruction(
                        kind="ASSIGN",
                        target_id=sym.id_code,
                        target_type=sym.data_type,
                        expr=resolved_expr,
                        scope=scope,
                    )
                )
                cleaned_statements.append(f"{sym.id_code} = {resolved_expr}")
                continue

            return ExtendedValidationResult(
                is_valid=False,
                class_name=class_name,
                errors=[f"Error sintáctico en línea {line_num}: instrucción no válida '{stmt_line}'."],
                error_line=line_num,
            )

        return None

    def _invoke_method(
        self,
        called_meth: str,
        raw_args: str,
        clean_code: str,
        caller_scope: str,
        scopes: Dict[str, Dict[str, SymbolEntry]],
        register_symbol,
        sym_by_id: Dict[str, SymbolEntry],
        next_id,
        methods_info: Dict[str, dict],
        instructions: List[IRInstruction],
        cleaned_statements: List[str],
        class_name: str,
        main_class_id: str,
        line_num: int,
        emitted_methods: Set[str],
    ) -> Optional[ExtendedValidationResult]:
        minfo = methods_info[called_meth]
        params = minfo["params"]
        arg_list = [a.strip() for a in raw_args.split(",")] if raw_args.strip() else []
        if len(arg_list) != len(params):
            return ExtendedValidationResult(
                is_valid=False,
                class_name=class_name,
                errors=[
                    f"Error semántico en línea {line_num}: '{called_meth}' espera {len(params)} argumento(s), recibió {len(arg_list)}."
                ],
                error_line=line_num,
            )
        for p_sym, arg_expr in zip(params, arg_list):
            resolved_arg, err = self._resolve_expression(arg_expr, caller_scope, scopes, class_name, main_class_id)
            if err:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error en línea {line_num}: {err}"],
                    error_line=line_num,
                )
            type_err = self._check_assignment_types(p_sym.data_type, resolved_arg, sym_by_id)
            if type_err:
                return ExtendedValidationResult(
                    is_valid=False,
                    class_name=class_name,
                    errors=[f"Error semántico en línea {line_num}: {type_err}"],
                    error_line=line_num,
                )
            instructions.append(
                IRInstruction(
                    kind="ASSIGN",
                    target_id=p_sym.id_code,
                    target_type=p_sym.data_type,
                    expr=resolved_arg,
                    scope=called_meth,
                )
            )
            cleaned_statements.append(f"{p_sym.id_code} = {resolved_arg}")

        if called_meth not in emitted_methods:
            emitted_methods.add(called_meth)
            return self._parse_block_statements(
                clean_code=clean_code,
                start_idx=minfo["body_start"],
                end_idx=minfo["body_end"],
                scope=called_meth,
                scopes=scopes,
                register_symbol=register_symbol,
                sym_by_id=sym_by_id,
                next_id=next_id,
                instructions=instructions,
                cleaned_statements=cleaned_statements,
                class_name=class_name,
                main_class_id=main_class_id,
                methods_info=methods_info,
                method_entry=minfo["entry"],
                emitted_methods=emitted_methods,
            )
        return None

    def _lookup_symbol(self, name: str, scope: str, scopes: Dict[str, Dict[str, SymbolEntry]]) -> Optional[SymbolEntry]:
        if scope in scopes and name in scopes[scope]:
            return scopes[scope][name]
        if name in scopes["Global"]:
            return scopes["Global"][name]
        return None

    def _resolve_expression(
        self,
        expr: str,
        scope: str,
        scopes: Dict[str, Dict[str, SymbolEntry]],
        class_name: str,
        main_class_id: str,
    ) -> Tuple[str, Optional[str]]:
        expr = expr.strip()
        if not expr:
            return "", "expresión vacía."

        no_strings = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "STR", expr)
        if re.match(r"^(?:[*/%+]|>=|<=|==|!=|<|>)", no_strings) or re.search(r"(?:[+\-*/%=!<>]|>=|<=|==|!=)$", no_strings):
            return "", f"expresión mal formada '{expr}'."
        if re.search(r"[*/%]\s*[+\-*/%]", no_strings) or re.search(r"[+\-]\s*[*/%]", no_strings):
            return "", f"operadores consecutivos inválidos en '{expr}'."

        token_pattern = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b[A-Za-z_]\w*\b')
        error_msg: Optional[str] = None

        def replacer(match: re.Match) -> str:
            nonlocal error_msg
            tok = match.group(0)
            if tok.startswith('"') or tok.startswith("'"):
                return tok
            if tok in self.RESERVED or re.match(r"^ID\d+$", tok):
                return tok
            if tok == class_name:
                return main_class_id
            sym = self._lookup_symbol(tok, scope, scopes)
            if sym is None:
                error_msg = f"identificador '{tok}' no declarado en el ámbito '{scope}'."
                return tok
            return sym.id_code

        resolved = token_pattern.sub(replacer, expr)
        if error_msg:
            return "", error_msg
        return resolved, None

    def _check_assignment_types(
        self,
        target_type: str,
        resolved_expr: str,
        sym_by_id: Dict[str, SymbolEntry],
    ) -> Optional[str]:
        expr_type = self._infer_expr_type(resolved_expr, sym_by_id)
        if expr_type is None:
            return None

        if target_type == "boolean":
            if expr_type != "boolean":
                return f"tipos incompatibles: no se puede asignar '{expr_type}' a 'boolean'."
            return None

        if target_type == "String":
            if expr_type != "String":
                return f"tipos incompatibles: no se puede asignar '{expr_type}' a 'String'."
            return None

        if target_type == "char":
            if expr_type != "char":
                return f"tipos incompatibles: no se puede asignar '{expr_type}' a 'char'."
            return None

        if target_type in self.NUMERIC_TYPES:
            if expr_type not in self.NUMERIC_TYPES:
                return f"tipos incompatibles: no se puede asignar '{expr_type}' a '{target_type}'."
            widening = {
                "double": {"double", "float", "long", "int", "short", "byte", "char"},
                "float": {"float", "long", "int", "short", "byte", "char"},
                "long": {"long", "int", "short", "byte", "char"},
                "int": {"int", "short", "byte", "char"},
                "short": {"short", "byte"},
                "byte": {"byte"},
            }
            if target_type == "byte" and expr_type == "int" and re.match(r"^-?\d+$", resolved_expr.strip()):
                val = int(resolved_expr.strip())
                if -128 <= val <= 127:
                    return None
            if expr_type not in widening.get(target_type, {target_type}):
                return f"tipos incompatibles: pérdida de precisión de '{expr_type}' a '{target_type}'."
        return None

    def _infer_expr_type(self, expr: str, sym_by_id: Dict[str, SymbolEntry]) -> Optional[str]:
        s = re.sub(r"\(\s*(?:float|double|int|char|long|short|byte|boolean)\s*\)", "", expr).strip()
        if re.search(r"(?:>=|<=|==|!=|<|>)", s) or s.startswith("!"):
            return "boolean"
        if s in ("true", "false"):
            return "boolean"
        if re.match(r'^"(?:\\.|[^"\\])*"$', s):
            return "String"
        if re.match(r"^'(?:\\.|[^'\\])*'$", s):
            return "char"
        if re.match(r"^-?\d+(?:\.\d+)?[fF]$", s):
            return "float"
        if re.match(r"^-?\d+\.\d+$", s):
            return "double"
        if re.match(r"^-?\d+$", s):
            return "int"

        tokens = re.findall(
            r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\d+\.\d+[fF]?|\d+[fF]?|\.[A-Za-z_]\w*\(\)|[A-Za-z_]\w*',
            s,
        )
        inferred: Set[str] = set()
        for t in tokens:
            if t.startswith('"'):
                inferred.add("String")
            elif t.startswith("'"):
                inferred.add("char")
            elif t in ("true", "false"):
                inferred.add("boolean")
            elif t.lower().endswith("f") and re.match(r"^\d", t):
                inferred.add("float")
            elif "." in t and re.match(r"^\d", t):
                inferred.add("double")
            elif re.match(r"^\d+$", t):
                inferred.add("int")
            elif t == ".length()":
                inferred.clear()
                inferred.add("int")
            elif t == "random":
                inferred.add("double")
            elif t in sym_by_id:
                dt = sym_by_id[t].data_type
                if dt in self.VALID_TYPES:
                    inferred.add(dt)

        if "String" in inferred:
            return "String"
        if "boolean" in inferred:
            return "boolean" if len(inferred) == 1 else "invalid"
        if "double" in inferred:
            return "double"
        if "float" in inferred:
            return "float"
        if "long" in inferred:
            return "long"
        if "int" in inferred:
            return "int"
        if "char" in inferred and len(inferred) == 1:
            return "char"
        if "byte" in inferred and len(inferred) == 1:
            return "byte"
        return None

    def _strip_comments_preserve_lines(self, code: str) -> str:
        """Elimina // y /* ... */ ignorando los que estén dentro de cadenas o caracteres."""
        pattern = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*')

        def repl(m: re.Match) -> str:
            tok = m.group(0)
            if tok.startswith('"') or tok.startswith("'"):
                return tok
            if tok.startswith("/*"):
                return "\n" * tok.count("\n")
            return ""

        return pattern.sub(repl, code)

    def _find_unclosed_quotes(self, code: str) -> Optional[int]:
        for line_no, line in enumerate(code.splitlines(), start=1):
            in_str = False
            in_chr = False
            esc = False
            for ch in line:
                if esc:
                    esc = False
                    continue
                if ch == "\\":
                    esc = True
                    continue
                if ch == '"' and not in_chr:
                    in_str = not in_str
                elif ch == "'" and not in_str:
                    in_chr = not in_chr
            if in_str or in_chr:
                return line_no
        return None

    def _find_matching_brace(self, code: str, open_idx: int) -> Optional[int]:
        depth = 0
        for i in range(open_idx, len(code)):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
        return None

    def _find_illegal_chars(self, code: str) -> Optional[int]:
        cleaned = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "", code)
        for line_no, line in enumerate(cleaned.splitlines(), start=1):
            if re.search(r"[@$#¿?¡]", line):
                return line_no
        return None

    def _find_unbalanced_line(self, code: str, open_ch: str, close_ch: str) -> int:
        depth = 0
        last_open_line = 1
        for line_no, line in enumerate(code.splitlines(), start=1):
            for ch in line:
                if ch == open_ch:
                    depth += 1
                    last_open_line = line_no
                elif ch == close_ch:
                    depth -= 1
                    if depth < 0:
                        return line_no
        return last_open_line

    def _line_of_snippet(self, code: str, snippet: str) -> int:
        idx = code.find(snippet)
        return 1 if idx == -1 else code[:idx].count("\n") + 1