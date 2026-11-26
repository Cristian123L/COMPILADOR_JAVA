import re
from backend.entities.validation_result import ValidationResult


class JavaValidator:
    """
    Valida que el código de entrada sea una clase principal de Java depurada
    antes de permitir la generación de código intermedio.
    """

    VALID_TYPES = {"int", "double", "float", "long", "short", "byte", "boolean", "char", "String"}

    def validate(self, source_code: str) -> ValidationResult:
        errors = []
        if not source_code or not source_code.strip():
            return ValidationResult(is_valid=False, errors=["El editor de código está vacío."])

        clean_code = self._strip_comments(source_code)

        if clean_code.count("{") != clean_code.count("}"):
            errors.append("Error de sintaxis: llaves '{' y '}' desbalanceadas.")
        if clean_code.count("(") != clean_code.count(")"):
            errors.append("Error de sintaxis: paréntesis '(' y ')' desbalanceados.")

        if errors:
            return ValidationResult(is_valid=False, errors=errors)

        class_match = re.search(
            r"\bpublic\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{",
            clean_code
        )
        if not class_match:
            errors.append("No se encontró una declaración válida de clase principal ('public class Nombre {').")
            return ValidationResult(is_valid=False, errors=errors)

        class_name = class_match.group(1)

        main_pattern = re.compile(
            r"\bpublic\s+static\s+void\s+main\s*\(\s*String\s*(?:\[\s*\]\s*[A-Za-z_]\w*|[A-Za-z_]\w*\s*\[\s*\])\s*\)\s*\{"
        )
        main_match = main_pattern.search(clean_code)
        if not main_match:
            errors.append("La clase principal debe contener el método 'public static void main(String[] args)'.")
            return ValidationResult(is_valid=False, class_name=class_name, errors=errors)

        main_body = self._extract_block_content(clean_code, main_match.end() - 1)
        if main_body is None:
            errors.append("No se pudo delimitar el bloque del método main.")
            return ValidationResult(is_valid=False, class_name=class_name, errors=errors)

        cleaned_statements = self._validate_statements(main_body, errors)

        if errors:
            return ValidationResult(is_valid=False, class_name=class_name, errors=errors)

        if not cleaned_statements:
            errors.append("El método main no contiene sentencias ejecutables para generar código intermedio.")
            return ValidationResult(is_valid=False, class_name=class_name, errors=errors)

        return ValidationResult(
            is_valid=True,
            class_name=class_name,
            errors=[],
            cleaned_statements=cleaned_statements
        )

    def _strip_comments(self, code: str) -> str:
        code = re.sub(r"/\*[\s\S]*?\*/", "", code)
        code = re.sub(r"//.*", "", code)
        return code

    def _extract_block_content(self, code: str, open_brace_index: int):
        depth = 0
        for i in range(open_brace_index, len(code)):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    return code[open_brace_index + 1:i]
        return None

    def _validate_statements(self, body: str, errors: list) -> list[str]:
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        cleaned = []
        declared_vars = set()

        for idx, line in enumerate(lines, start=1):
            if not line.endswith(";"):
                errors.append(f"Línea {idx} dentro de main ('{line}'): falta punto y coma ';' al final.")
                continue

            stmt = line[:-1].strip()
            if not stmt:
                continue

            # Detectar System.out.println(...) o System.out.print(...) para rastrear uso real de variables (CM)
            print_match = re.match(r"^System\.out\.print(?:ln)?\s*\((.+)\)$", stmt)
            if print_match:
                expr = print_match.group(1).strip()
                if not self._is_valid_expression(expr):
                    errors.append(f"Expresión inválida en impresión '{expr}' en '{line}'.")
                    continue
                cleaned.append(f"PRINT {expr}")
                continue

            # Caso A: Declaración con o sin inicialización -> ej: int a = 5 + 3; o int x;
            decl_match = re.match(r"^([A-Za-z_]\w*)\s+([A-Za-z_]\w*)(?:\s*=\s*(.+))?$", stmt)
            if decl_match:
                var_type, var_name, expr = decl_match.groups()
                if var_type not in self.VALID_TYPES:
                    errors.append(f"Tipo de dato no reconocido '{var_type}' en '{line}'.")
                    continue
                if var_name in declared_vars:
                    errors.append(f"Variable '{var_name}' declarada duplicada en '{line}'.")
                    continue
                declared_vars.add(var_name)
                if expr is not None:
                    if not self._is_valid_expression(expr):
                        errors.append(f"Expresión inválida '{expr}' en '{line}'.")
                        continue
                    cleaned.append(f"{var_name} = {expr.strip()}")
                continue

            # Caso B: Asignación simple -> ej: area = base * altura + 2;
            assign_match = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", stmt)
            if assign_match:
                var_name, expr = assign_match.groups()
                if var_name not in declared_vars:
                    errors.append(f"Variable '{var_name}' no declarada antes de su uso en '{line}'.")
                    continue
                if not self._is_valid_expression(expr):
                    errors.append(f"Expresión inválida '{expr}' en '{line}'.")
                    continue
                cleaned.append(f"{var_name} = {expr.strip()}")
                continue

            errors.append(f"Sentencia no válida o no depurada en '{line}'.")

        return cleaned

    def _is_valid_expression(self, expr: str) -> bool:
        expr = expr.strip()
        if not expr:
            return False
        if re.match(r"^[*/%+]", expr) or re.search(r"[+\-*/%=]$", expr):
            return False
        if re.search(r"[+\-*/%]\s*[+\-*/%]", expr):
            return False
        if not re.match(r"^[A-Za-z0-9_.\s+\-*/%()\"']+$", expr):
            return False
        return True