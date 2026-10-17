"""
routers/eventos.py
POST /eventos : el ESP32 reporta lo que SOLO él puede saber
                (ERROR_SENSOR, REINICIO, REINTENTO, ERROR_ENVIO).
GET  /eventos : consulta del log.
Nota: DESCONEXION/CONEXION las infiere la API sola en POST /lecturas,
porque un dispositivo sin red no puede avisar que se cayó.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Dispositivo, EventoSistema
from routers.lecturas import MAX_ANTIGUEDAD, MAX_ADELANTO
from schemas.evento import EventoCreate

router = APIRouter(prefix="/eventos", tags=["Eventos"])


@router.post("", status_code=201)
def crear_evento(payload: EventoCreate, db: Session = Depends(get_db)):
    ahora = datetime.now(timezone.utc)
    tiempo = payload.tiempo or ahora
    if tiempo.tzinfo is None:
        tiempo = tiempo.replace(tzinfo=timezone.utc)
    if tiempo > ahora + MAX_ADELANTO or tiempo < ahora - MAX_ANTIGUEDAD:
        raise HTTPException(422, detail="'tiempo' fuera de rango aceptable")
    if db.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(404, detail="Dispositivo no registrado")

    ev = EventoSistema(dispositivo_id=payload.dispositivo_id, tipo_evento=payload.tipo_evento,
                       mensaje=payload.mensaje, tiempo=tiempo)
    db.add(ev)
    db.commit()
    return {"id": ev.id, "tiempo": ev.tiempo}


@router.get("")
def listar_eventos(dispositivo_id: int, limite: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db)):
    filas = (db.query(EventoSistema)
             .filter(EventoSistema.dispositivo_id == dispositivo_id)
             .order_by(EventoSistema.tiempo.desc()).limit(limite).all())
    return [{"id": e.id, "tipo_evento": e.tipo_evento, "mensaje": e.mensaje, "tiempo": e.tiempo}
            for e in filas]
