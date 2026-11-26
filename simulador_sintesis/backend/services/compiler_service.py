from dataclasses import dataclass, field
from typing import List
from backend.entities.optimization_row import OptimizationRow
from backend.entities.validation_result import ValidationResult
from backend.generators.code_generators import IntermediateCodeGenerator
from backend.optimizer.optimizer_engine import OptimizerEngine
from backend.validator.java_validator import JavaValidator


@dataclass
class SynthesisResult:
    validation: ValidationResult
    mode: str
    intermediate_lines: List[str] = field(default_factory=list)
    optimization_locked: bool = False
    optimization_rows: List[OptimizationRow] = field(default_factory=list)
    runtime_error: str = ""


class CompilerSynthesisService:
    MODE_CUADRUPLOS = "CUADRUPLOS"
    MODE_TRIPLOS = "TRIPLOS"
    MODE_TRES_DIRECCIONES = "TRES_DIRECCIONES"

    def __init__(self):
        self.validator = JavaValidator()
        self.generator = IntermediateCodeGenerator()
        self.optimizer = OptimizerEngine()

    def process(self, source_code: str, mode: str) -> SynthesisResult:
        # Inciso 1: Validación estricta antes de procesar cualquier siguiente inciso
        validation = self.validator.validate(source_code)
        if not validation.is_valid:
            return SynthesisResult(
                validation=validation,
                mode=mode,
                optimization_locked=(mode == self.MODE_TRES_DIRECCIONES),
            )

        try:
            # Inciso 3: Bloquear optimización por defecto si es Tres Direcciones
            if mode == self.MODE_TRES_DIRECCIONES:
                tres_dir = self.generator.generate_tres_direcciones(validation.cleaned_statements)
                return SynthesisResult(
                    validation=validation,
                    mode=mode,
                    intermediate_lines=[str(item) for item in tres_dir],
                    optimization_locked=True,
                    optimization_rows=[],
                )

            if mode == self.MODE_TRIPLOS:
                triplos = self.generator.generate_triplos(validation.cleaned_statements)
                cuad_equiv = self.generator.generate_cuadruplos(validation.cleaned_statements)
                opt_rows = self.optimizer.optimize_triplos(triplos, cuad_equiv)
                return SynthesisResult(
                    validation=validation,
                    mode=mode,
                    intermediate_lines=[str(item) for item in triplos],
                    optimization_locked=False,
                    optimization_rows=opt_rows,
                )

            # Default: CUADRUPLOS
            cuadruplos = self.generator.generate_cuadruplos(validation.cleaned_statements)
            opt_rows, _ = self.optimizer.optimize_cuadruplos(cuadruplos)
            return SynthesisResult(
                validation=validation,
                mode=mode,
                intermediate_lines=[str(item) for item in cuadruplos],
                optimization_locked=False,
                optimization_rows=opt_rows,
            )

        except ValueError as exc:
            return SynthesisResult(
                validation=validation,
                mode=mode,
                optimization_locked=(mode == self.MODE_TRES_DIRECCIONES),
                runtime_error=str(exc),
            )