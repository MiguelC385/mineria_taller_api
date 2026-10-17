"""schemas/consulta.py - Registro de las teclas que el ESP32 resuelve solo (1 y 7)."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RegistroTecla(BaseModel):
    dispositivo_id: int
    tecla: str = Field(min_length=1, max_length=2)
    resultado: Optional[str] = Field(default=None, max_length=100)   # lo que se mostró en el LCD
    tiempo: Optional[datetime] = None    # hora en que se presionó (si estuvo sin conexión)
