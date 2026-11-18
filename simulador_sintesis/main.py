from pathlib import Path
from backend.validator.java_validator import JavaValidator

BASE_DIR = Path(__file__).resolve().parent
ruta_archivo = BASE_DIR / "samples" / "prueba_valida.java"

with open(ruta_archivo, "r", encoding="utf-8") as f:
    codigo = f.read()

validador = JavaValidator()
resultado = validador.validate(codigo)

print("¿Es válido?:", resultado.is_valid)
print("Clase:", resultado.class_name)
print("Errores:", resultado.errors)
print("Sentencias limpias:", resultado.cleaned_statements)