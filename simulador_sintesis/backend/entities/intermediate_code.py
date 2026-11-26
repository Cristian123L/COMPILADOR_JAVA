from dataclasses import dataclass


@dataclass
class Triplo:
    indice: int
    val1: str
    ope: str
    val2: str

    def __str__(self) -> str:
        return f"{self.indice}. ({self.val1}, {self.ope}, {self.val2})"


@dataclass
class Cuadruplo:
    indice: int
    val1: str
    ope: str
    val2: str
    res: str

    def __str__(self) -> str:
        return f"{self.indice}. ({self.val1}, {self.ope}, {self.val2}, {self.res})"


@dataclass
class TresDirecciones:
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