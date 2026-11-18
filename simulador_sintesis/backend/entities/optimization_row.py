from dataclasses import dataclass


@dataclass
class OptimizationRow:
    """Representa una fila de la tabla de optimización."""
    cuadruplo_original: str
    acronimo_optimizacion: str   # Ej: PC (Propagación Constantes), RP (Reducción Potencias), '-'
    cuadruplo_afectado: str      # Número del cuádruplo/triplo afectado o '-'
    cuadruplo_modificado: str    # Nuevo código modificado o 'ELIMINADO'