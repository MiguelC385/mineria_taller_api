"""
routers/lecturas.py
POST /lecturas  -> recibe las 3 variables de un ciclo en UN solo envío.

Reglas (según el diseño de la BD):
  1. variables.valor_min/max   = rango FÍSICO  -> fuera de él se RECHAZA el dato.
  2. umbrales_alerta           = rango ESPERADO -> el dato se GUARDA y se genera alerta.
  3. La variable debe pertenecer a un sensor instalado en ese dispositivo
     (esta integridad se valida aquí porque la hypertable no puede duplicar columnas).
  4. INSERT ... ON CONFLICT DO NOTHING: si el ESP32 reintenta, no hay duplicados.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from database import get_db
from decimales import redondear, texto
from models import (Dispositivo, DispositivoSensor, Variable, Lectura, UmbralAlerta,
                    Alerta, EventoSistema)
from schemas.lectura import LecturaBatchCreate, LecturaBatchResponse, LecturaRechazada

router = APIRouter(prefix="/lecturas", tags=["Lecturas"])

# Protege la hypertable de horas absurdas (p. ej. 1970 si falla el NTP del ESP32,
# lo que crearía un chunk en 1970). Se aceptan reenvíos de hasta 7 días atrás.
MAX_ANTIGUEDAD = timedelta(days=7)
MAX_ADELANTO = timedelta(minutes=5)
# Si pasan más de 90 s sin datos (4-5 ciclos de 20 s) se considera una caída.
UMBRAL_DESCONEXION = timedelta(seconds=90)


def _evaluar_alertas(db: Session, dispositivo_id: int, tiempo: datetime,
                     valores: Dict[int, float]) -> int:
    """
    Compara cada valor nuevo con sus umbrales activos.
    Una alerta es un EPISODIO: se abre al salir del umbral (si no hay una activa)
    y se cierra al volver al rango. Así 'alertas activas' (tecla 6) no se infla
    con una fila nueva cada 20 segundos.
    """
    umbrales = (
        db.query(UmbralAlerta)
        .filter(UmbralAlerta.variable_id.in_(valores.keys()), UmbralAlerta.activo.is_(True))
        .all()
    )
    nuevas = 0
    for u in umbrales:
        valor = valores[u.variable_id]
        fuera = valor < u.umbral_min or valor > u.umbral_max
        abierta = (
            db.query(Alerta)
            .filter(Alerta.dispositivo_id == dispositivo_id,
                    Alerta.umbral_id == u.id,
                    Alerta.activa.is_(True))
            .first()
        )
        if fuera and abierta is None:
            db.add(Alerta(tiempo=tiempo, dispositivo_id=dispositivo_id,
                          variable_id=u.variable_id, umbral_id=u.id, valor=valor,
                          tipo="BAJO" if valor < u.umbral_min else "ALTO"))
            nuevas += 1
        elif not fuera and abierta is not None:
            abierta.activa = False
            abierta.resuelta_en = tiempo
    return nuevas


def _registrar_reconexion(db: Session, dispositivo_id: int, ahora: datetime) -> None:
    """
    Un ESP32 sin red no puede avisar que se cayó, así que la API lo infiere:
    si el último dato recibido es viejo, registra DESCONEXION (con la hora del último
    dato) y CONEXION (ahora). Se ejecuta ANTES de insertar los datos nuevos.
    """
    ultimo = db.execute(
        text("SELECT max(recibido_en) FROM lecturas "
             "WHERE dispositivo_id = :d AND tiempo > now() - interval '7 days'"),
        {"d": dispositivo_id}).scalar()
    if ultimo is None:
        db.add(EventoSistema(dispositivo_id=dispositivo_id, tipo_evento="CONEXION",
                             mensaje="Primer dato recibido (sin datos en los últimos 7 días)"))
    elif ahora - ultimo > UMBRAL_DESCONEXION:
        seg = int((ahora - ultimo).total_seconds())
        db.add(EventoSistema(dispositivo_id=dispositivo_id, tipo_evento="DESCONEXION",
                             mensaje=f"Inferida por la API: {seg} s sin datos", tiempo=ultimo))
        db.add(EventoSistema(dispositivo_id=dispositivo_id, tipo_evento="CONEXION",
                             mensaje=f"Reconexión tras {seg} s sin datos"))


@router.post("", response_model=LecturaBatchResponse, status_code=status.HTTP_201_CREATED)
def crear_lecturas(payload: LecturaBatchCreate, db: Session = Depends(get_db)):
    ahora = datetime.now(timezone.utc)

    # --- Hora de la medición ---
    tiempo = payload.tiempo or ahora
    if tiempo.tzinfo is None:
        tiempo = tiempo.replace(tzinfo=timezone.utc)
    if tiempo > ahora + MAX_ADELANTO or tiempo < ahora - MAX_ANTIGUEDAD:
        raise HTTPException(422,
                            detail="'tiempo' fuera de rango aceptable (¿falló el NTP del ESP32?)")

    # --- Dispositivo ---
    if db.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dispositivo no registrado")

    # --- Variables válidas para ESTE dispositivo (sensor instalado) ---
    nombres = [l.variable for l in payload.lecturas]
    variables = (
        db.query(Variable)
        .join(DispositivoSensor, DispositivoSensor.sensor_id == Variable.sensor_id)
        .filter(DispositivoSensor.dispositivo_id == payload.dispositivo_id,
                Variable.nombre.in_(nombres))
        .all()
    )
    por_nombre = {v.nombre: v for v in variables}

    validas, rechazadas = [], []
    for item in payload.lecturas:
        var = por_nombre.get(item.variable)
        if var is None:
            rechazadas.append(LecturaRechazada(
                variable=item.variable,
                motivo="Variable inexistente o sensor no instalado en este dispositivo"))
        elif not (var.valor_min <= redondear(item.valor) <= var.valor_max):
            rechazadas.append(LecturaRechazada(
                variable=item.variable,
                motivo=f"Fuera del rango físico [{texto(var.valor_min)}, {texto(var.valor_max)}] {var.unidad}"))
        else:
            validas.append((var, redondear(item.valor)))   # siempre con un decimal

    if not validas:
        raise HTTPException(422,
                            detail=[r.model_dump() for r in rechazadas])

    _registrar_reconexion(db, payload.dispositivo_id, ahora)

    # --- Inserción idempotente ---
    stmt = (
        pg_insert(Lectura)
        .values([{"tiempo": tiempo, "dispositivo_id": payload.dispositivo_id,
                  "variable_id": v.id, "valor": val} for v, val in validas])
        .on_conflict_do_nothing(index_elements=["dispositivo_id", "variable_id", "tiempo"])
        .returning(Lectura.variable_id, Lectura.valor)
    )
    nuevas_filas = db.execute(stmt).all()   # RETURNING solo devuelve las realmente insertadas

    # Alertas solo sobre lo recién insertado (un reintento no las reevalúa)
    alertas_nuevas = 0
    if nuevas_filas:
        alertas_nuevas = _evaluar_alertas(
            db, payload.dispositivo_id, tiempo,
            {fila.variable_id: fila.valor for fila in nuevas_filas})

    db.commit()

    return LecturaBatchResponse(
        tiempo=tiempo,
        insertadas=len(nuevas_filas),
        duplicadas=len(validas) - len(nuevas_filas),
        rechazadas=rechazadas,
        alertas_nuevas=alertas_nuevas,
    )