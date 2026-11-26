from dataclasses import dataclass


@dataclass
class Triplo:
    """Representa n. (val1, ope, val2) con n >= 1 sin límite de registros."""
    indice: int
    val1: str
    ope: str
    val2: str

    def __str__(self) -> str:
        return f"{self.indice}. ({self.val1}, {self.ope}, {self.val2})"


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
    """
    Representa instrucciones de Tres Direcciones con restricción 1 <= n <= 3:
    - Asignación directa: ID2 = 3  o  ID3 = T1
    - Operación temporal: T1. (ID2, +, 1)
    - Retorno / Salida:   ID4 SOUT T2  o  ID4 RTN T1
    """
    registro: int
    val1: str
    ope: str
    val2: str
    is_direct_assign: bool = False
    is_special_stmt: bool = False

    def __post_init__(self):
        if self.registro != 0 and not (1 <= self.registro <= 3):
            raise ValueError(
                f"Violación de regla: el registro T{self.registro} excede el límite permitido (1 <= n <= 3)."
            )

    def __str__(self) -> str:
        if self.is_direct_assign:
            return f"{self.val1} = {self.val2}"
        if self.is_special_stmt:
            return f"{self.val1} {self.ope} {self.val2}".strip()
        return f"T{self.registro}. ({self.val1}, {self.ope}, {self.val2})"