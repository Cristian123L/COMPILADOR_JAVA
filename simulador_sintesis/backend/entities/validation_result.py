from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationResult:
    is_valid: bool
    class_name: str = ""
    errors: List[str] = field(default_factory=list)
    cleaned_statements: List[str] = field(default_factory=list)