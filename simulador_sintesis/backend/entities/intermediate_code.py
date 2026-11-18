from dataclasses import dataclass


@dataclass
class Triplo:
    """Representa n(val1, ope, val2) con n >= 1 sin límite de registros."""
    indice: int
    val1: str
    ope: str
    val2: str

    def __str__(self) -> str:
        return f"{self.indice}({self.val1}, {self.ope}, {self.val2})"


@dataclass
class Cuadruplo:
    """Representa n. (val1, ope, val2, res) con n >= 1 sin límite de registros."""
    indice: int
    val1: str
    ope: str
    val2: str
    res: str

    def __str__(self) -> str:
        return f"{self.indice}. ({self.val1}, {self.ope}, {self.val2}, {self.res})"


@dataclass
class TresDirecciones:
    """Representa Tn. val1 ope val2 con restricción estricta 1 <= n <= 3."""
    registro: int
    val1: str
    ope: str
    val2: str

    def __post_init__(self):
        if not (1 <= self.registro <= 3):
            raise ValueError(
                f"Violación de regla: el registro T{self.registro} excede el límite permitido (1 <= n <= 3)."
            )

    def __str__(self) -> str:
        if self.ope:
            return f"T{self.registro}. {self.val1} {self.ope} {self.val2}".strip()
        return f"T{self.registro}. {self.val1}"