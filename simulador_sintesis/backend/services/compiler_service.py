from dataclasses import dataclass, field
from typing import List
from backend.entities.optimization_row import OptimizationRow
from backend.entities.symbol_entry import SymbolEntry
from backend.generators.code_generators import IntermediateCodeGenerator
from backend.optimizer.optimizer_engine import OptimizerEngine
from backend.validator.java_validator import ExtendedValidationResult, JavaValidator


@dataclass
class SynthesisResult:
    validation: ExtendedValidationResult
    mode: str
    intermediate_lines: List[str] = field(default_factory=list)
    footer_line: str = ""
    symbols: List[SymbolEntry] = field(default_factory=list)
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
        validation = self.validator.validate(source_code)
        if not validation.is_valid:
            return SynthesisResult(
                validation=validation,
                mode=mode,
                optimization_locked=(mode == self.MODE_TRES_DIRECCIONES),
            )

        try:
            if mode == self.MODE_TRES_DIRECCIONES:
                tres_dir, footer = self.generator.generate_tres_direcciones(
                    validation.instructions, validation.main_class_id
                )
                lines = [str(item) for item in tres_dir]
                if footer:
                    lines.append(footer)
                return SynthesisResult(
                    validation=validation,
                    mode=mode,
                    intermediate_lines=lines,
                    footer_line=footer,
                    symbols=validation.symbols,
                    optimization_locked=True,
                    optimization_rows=[],
                )

            if mode == self.MODE_TRIPLOS:
                triplos, footer = self.generator.generate_triplos(
                    validation.instructions, validation.main_class_id
                )
                opt_rows = self.optimizer.optimize_triplos(triplos)
                lines = [str(item) for item in triplos]
                if footer:
                    lines.append(footer)
                return SynthesisResult(
                    validation=validation,
                    mode=mode,
                    intermediate_lines=lines,
                    footer_line=footer,
                    symbols=validation.symbols,
                    optimization_locked=False,
                    optimization_rows=opt_rows,
                )

            cuadruplos, footer = self.generator.generate_cuadruplos(
                validation.instructions, validation.symbols, validation.main_class_id
            )
            opt_rows = self.optimizer.optimize_cuadruplos(cuadruplos)
            lines = [str(item) for item in cuadruplos]
            if footer:
                lines.append(footer)
            return SynthesisResult(
                validation=validation,
                mode=mode,
                intermediate_lines=lines,
                footer_line=footer,
                symbols=validation.symbols,
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