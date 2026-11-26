from dataclasses import dataclass


@dataclass
class SymbolEntry:
    id_code: str        
    lexeme: str         
    category: str       
    data_type: str      
    scope: str          
    initial_value: str = "-"