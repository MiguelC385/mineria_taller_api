"""schemas/evento.py - Eventos que el ESP32 puede reportar (mismos valores del CHECK en SQL)."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

TipoEvento = Literal["CONEXION", "DESCONEXION", "ERROR_ENVIO",
                     "REINTENTO", "ERROR_SENSOR", "REINICIO"]


class EventoCreate(BaseModel):
    dispositivo_id: int
    tipo_evento: TipoEvento
    mensaje: Optional[str] = Field(default=None, max_length=300)
    tiempo: Optional[datetime] = None   # hora real del evento (si estuvo offline)
