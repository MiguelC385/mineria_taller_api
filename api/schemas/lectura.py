"""
schemas/lectura.py
Contrato JSON del ESP32. El formato actual del .ino ya es compatible:
  {"dispositivo_id": 1,
   "lecturas": [{"variable": "temperatura", "valor": 24.5}, ...]}
Campo NUEVO y OPCIONAL: "tiempo" (ISO 8601, UTC) = hora real de la medición.
Si no se envía, la API usa la hora actual del servidor.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class LecturaItem(BaseModel):
    variable: str = Field(min_length=1, max_length=50)
    valor: float = Field(allow_inf_nan=False)


class LecturaBatchCreate(BaseModel):
    dispositivo_id: int
    tiempo: Optional[datetime] = None
    lecturas: List[LecturaItem] = Field(min_length=1)


class LecturaRechazada(BaseModel):
    variable: str
    motivo: str


class LecturaBatchResponse(BaseModel):
    tiempo: datetime
    insertadas: int
    duplicadas: int          # ya existían (reintento del ESP32): se ignoran sin error
    rechazadas: List[LecturaRechazada]
    alertas_nuevas: int
