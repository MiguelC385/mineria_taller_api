"""
routers/consultas.py
GET /consultas/{tecla}?dispositivo_id=1  -> atiende las teclas del teclado matricial.

Cada respuesta trae:
  datos      : resultado estructurado (para KNIME, Flowise, pruebas)
  pantallas  : lista de pantallas LCD 16x2 ya formateadas (cada línea <= 16 caracteres)
Con formato=lcd se devuelve solo el texto: 2 líneas por pantalla, separadas por \\n.

Formato de las pantallas (todas con unidades: C y %):
  Opción 2 y 5 : 1 número por variable -> las 3 variables caben en UNA pantalla.
  Opción 3 y 4 : 2 números por variable -> UNA pantalla por variable (título + valores).
  Opción 6     : UNA pantalla por alerta, con el tipo (ALTO / BAJO) en la segunda línea.
El contador de página (1/3) lo dibuja el ESP32 arriba a la derecha: por eso los títulos
de las pantallas con varias páginas no pasan de 12 caracteres.
Las teclas 1 y 7 las resuelve el propio ESP32; aquí se dejan para consultas desde el navegador.

Cada consulta se registra en consultas_menu. Solo se usa SQL estándar de PostgreSQL
(avg, stddev_samp, regr_slope, percentile_cont): funciona igual en local y en Neon.
Todas las consultas filtran por tiempo, para que TimescaleDB lea solo los chunks necesarios.
"""
import os
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from decimales import redondear, texto
from models import Dispositivo, OpcionMenu, ConsultaMenu
from routers.lecturas import MAX_ANTIGUEDAD, MAX_ADELANTO
from schemas.consulta import RegistroTecla

router = APIRouter(prefix="/consultas", tags=["Consultas del menú"])

ZONA = os.getenv("ZONA_HORARIA", "America/Bogota")   # define qué es "el día" (tecla 3)
UMBRAL_TENDENCIA = 0.5      # unidades/hora: por debajo de esto la tendencia es ESTABLE
VENTANA_ONLINE_S = 60       # 3 ciclos de 20 s sin datos => OFFLINE
LECTURAS_HORA = 180         # 3600 s / 20 s, por variable
MAX_PANTALLAS_LCD = 8       # el ESP32 guarda hasta 16 líneas = 8 pantallas
ABREV = {"temperatura": "T", "humedad_aire": "HA", "humedad_suelo": "HS"}
TITULO = {"temperatura": "Temp.", "humedad_aire": "H. aire", "humedad_suelo": "H. suelo"}


def _ab(nombre: str) -> str:
    return ABREV.get(nombre, nombre[:3].upper())


def _tit(nombre: str) -> str:
    return TITULO.get(nombre, nombre[:7].capitalize())


def _u(unidad) -> str:
    """El LCD solo muestra ASCII: °C -> C, % se queda igual."""
    return (unidad or "").replace("°", "")


def _lineas(tokens: List[str]) -> List[str]:
    """Empaqueta tokens en líneas de <=16 caracteres."""
    lineas, actual = [], ""
    for t in tokens:
        t = t[:16]
        if actual and len(actual) + 1 + len(t) <= 16:
            actual += " " + t
        else:
            if actual:
                lineas.append(actual)
            actual = t
    if actual:
        lineas.append(actual)
    return lineas


def _pares(lineas: List[str]) -> List[List[str]]:
    """Agrupa las líneas de a 2 (una pantalla del LCD 16x2). Sin líneas: 'Sin datos'."""
    if not lineas:
        lineas = ["Sin datos"]
    return [(lineas[i:i + 2] + [""])[:2] for i in range(0, len(lineas), 2)]


def _pantallas(tokens: List[str]) -> List[List[str]]:
    return _pares(_lineas(tokens))


# ---------------- Tecla 1: valor actual (el ESP32 la resuelve solo; aquí, para el navegador) ----------------
def _t1(db, d):
    filas = db.execute(text("""
        SELECT DISTINCT ON (l.variable_id) v.nombre, v.unidad, l.valor, l.tiempo
        FROM lecturas l JOIN variables v ON v.id = l.variable_id
        WHERE l.dispositivo_id = :d AND l.tiempo > now() - interval '1 day'
        ORDER BY l.variable_id, l.tiempo DESC"""), {"d": d}).all()
    datos = [{"variable": r.nombre, "unidad": r.unidad, "valor": redondear(r.valor), "tiempo": r.tiempo}
             for r in filas]
    return datos, _pantallas([f"{_ab(r.nombre)}:{texto(r.valor)}{_u(r.unidad)}" for r in filas])


# ---------------- Tecla 2: promedio última hora (1 número por variable: una pantalla) ----------------
def _t2(db, d):
    filas = db.execute(text("""
        SELECT v.nombre, v.unidad, avg(l.valor) AS promedio, count(*) AS n
        FROM lecturas l JOIN variables v ON v.id = l.variable_id
        WHERE l.dispositivo_id = :d AND l.tiempo > now() - interval '1 hour'
        GROUP BY v.id, v.nombre, v.unidad ORDER BY v.id"""), {"d": d}).all()
    datos = [{"variable": r.nombre, "unidad": r.unidad, "promedio": redondear(r.promedio), "n": r.n}
             for r in filas]
    tokens = [f"{_ab(r.nombre)}:{texto(r.promedio)}{_u(r.unidad)}" for r in filas]
    if tokens:
        tokens.append("Prom.1h")            # etiqueta: qué se está mostrando
    return datos, _pantallas(tokens)


# ---------------- Tecla 3: máximo y mínimo del día (2 números por variable: una pantalla cada una) ----------------
def _t3(db, d):
    filas = db.execute(text("""
        SELECT v.nombre, v.unidad, min(l.valor) AS minimo, max(l.valor) AS maximo
        FROM lecturas l JOIN variables v ON v.id = l.variable_id
        WHERE l.dispositivo_id = :d
          AND l.tiempo >= (date_trunc('day', now() AT TIME ZONE :tz) AT TIME ZONE :tz)
        GROUP BY v.id, v.nombre, v.unidad ORDER BY v.id"""), {"d": d, "tz": ZONA}).all()
    datos = [{"variable": r.nombre, "unidad": r.unidad, "minimo": redondear(r.minimo), "maximo": redondear(r.maximo)}
             for r in filas]
    pantallas = [[f"{_tit(r.nombre)} hoy",
                  f"Min{texto(r.minimo)} Max{texto(r.maximo)}{_u(r.unidad)}"] for r in filas]
    return datos, pantallas or _pares([])


# ---------------- Tecla 4: desviación estándar y tendencia (una pantalla por variable) ----------------
def _t4(db, d):
    filas = db.execute(text("""
        SELECT v.nombre, v.unidad, count(*) AS n,
               stddev_samp(l.valor) AS desviacion,
               regr_slope(l.valor, extract(epoch FROM l.tiempo)::double precision) * 3600
                   AS pendiente_hora
        FROM lecturas l JOIN variables v ON v.id = l.variable_id
        WHERE l.dispositivo_id = :d AND l.tiempo > now() - interval '1 hour'
        GROUP BY v.id, v.nombre, v.unidad ORDER BY v.id"""), {"d": d}).all()
    datos, pantallas = [], []
    for r in filas:
        p = r.pendiente_hora
        if p is None:
            tend = None
        elif p > UMBRAL_TENDENCIA:
            tend = "SUBE"
        elif p < -UMBRAL_TENDENCIA:
            tend = "BAJA"
        else:
            tend = "ESTABLE"
        datos.append({"variable": r.nombre, "unidad": r.unidad, "n": r.n,
                      "desviacion": redondear(r.desviacion), "pendiente_por_hora": redondear(p),
                      "tendencia": tend or "SIN DATOS"})
        pantallas.append([f"{_tit(r.nombre)} 1 h",
                          f"Desv {texto(r.desviacion)} {tend}" if tend else "Sin datos"])
    return datos, pantallas or _pares([])


# ---------------- Tecla 5: outliers (IQR, últimas 24 h) ----------------
def _t5(db, d):
    filas = db.execute(text("""
        WITH base AS (
            SELECT variable_id, valor FROM lecturas
            WHERE dispositivo_id = :d AND tiempo > now() - interval '24 hours'
        ), q AS (
            SELECT variable_id, count(*) AS n,
                   percentile_cont(0.25) WITHIN GROUP (ORDER BY valor) AS q1,
                   percentile_cont(0.75) WITHIN GROUP (ORDER BY valor) AS q3
            FROM base GROUP BY variable_id
        )
        SELECT v.nombre, v.unidad, q.n, q.q1, q.q3,
               count(*) FILTER (WHERE b.valor < q.q1 - 1.5 * (q.q3 - q.q1)
                                   OR b.valor > q.q3 + 1.5 * (q.q3 - q.q1)) AS atipicos
        FROM q JOIN base b ON b.variable_id = q.variable_id
               JOIN variables v ON v.id = q.variable_id
        GROUP BY v.id, v.nombre, v.unidad, q.n, q.q1, q.q3
        ORDER BY v.id"""), {"d": d}).all()
    datos = [{"variable": r.nombre, "unidad": r.unidad, "n": r.n, "q1": redondear(r.q1), "q3": redondear(r.q3),
              "limite_inferior": redondear(r.q1 - 1.5 * (r.q3 - r.q1)),
              "limite_superior": redondear(r.q3 + 1.5 * (r.q3 - r.q1)),
              "atipicos": r.atipicos, "metodo": "IQR 1.5, ventana 24 h"} for r in filas]
    if not filas:
        return datos, _pares([])
    return datos, _pares(["Atipicos 24h"] + _lineas([f"{_ab(r.nombre)}:{r.atipicos}" for r in filas]))


# ---------------- Tecla 6: alertas activas (una pantalla por alerta, con su tipo) ----------------
def _t6(db, d):
    filas = db.execute(text("""
        SELECT v.nombre, v.unidad, a.tipo, a.valor, a.tiempo
        FROM alertas a JOIN variables v ON v.id = a.variable_id
        WHERE a.dispositivo_id = :d AND a.activa
        ORDER BY a.tiempo DESC, a.id DESC"""), {"d": d}).all()      # la más reciente primero
    total = len(filas)
    por_variable = Counter(r.nombre for r in filas)
    datos = {"total_activas": total,
             "por_variable": [{"variable": n, "activas": c} for n, c in sorted(por_variable.items())],
             "alertas": [{"variable": r.nombre, "tipo": r.tipo, "valor": redondear(r.valor),
                          "unidad": r.unidad, "desde": r.tiempo} for r in filas],
             "mostradas_en_lcd": min(total, MAX_PANTALLAS_LCD)}
    if total == 0:
        return datos, [["Alertas: 0", "Todo normal"]]
    # 'valor' es el de la lectura que abrió la alerta, no el valor actual
    pantallas = [[f"Alertas: {total}", f"{_ab(r.nombre)} {r.tipo} {texto(r.valor)}{_u(r.unidad)}"]
                 for r in filas[:MAX_PANTALLAS_LCD]]
    return datos, pantallas


# ---------------- Tecla 7: estado de conexión (el ESP32 la resuelve solo; aquí, para el navegador) ----------------
def _t7(db, d):
    r = db.execute(text("""
        SELECT
          (SELECT max(recibido_en) FROM lecturas
            WHERE dispositivo_id = :d AND tiempo > now() - interval '7 days') AS ultimo,
          (SELECT count(*) FROM lecturas
            WHERE dispositivo_id = :d AND tiempo > now() - interval '1 hour') AS n_hora,
          (SELECT count(*) FROM variables v
             JOIN dispositivo_sensor ds ON ds.sensor_id = v.sensor_id
            WHERE ds.dispositivo_id = :d) AS n_vars,
          now() AS ahora"""), {"d": d}).one()
    ev = db.execute(text("""SELECT tipo_evento, tiempo FROM eventos_sistema
                            WHERE dispositivo_id = :d ORDER BY tiempo DESC LIMIT 1"""),
                    {"d": d}).first()
    if r.ultimo is None:
        estado, seg = "SIN DATOS", None
    else:
        seg = int((r.ahora - r.ultimo).total_seconds())
        estado = "ONLINE" if seg <= VENTANA_ONLINE_S else "OFFLINE"
    esperadas = r.n_vars * LECTURAS_HORA
    compl = min(100.0, round(100.0 * r.n_hora / esperadas, 1)) if esperadas else None
    datos = {"estado": estado, "segundos_desde_ultimo_dato": seg, "ultimo_dato_recibido": r.ultimo,
             "lecturas_ultima_hora": r.n_hora, "lecturas_esperadas_hora": esperadas,
             "completitud_pct": redondear(compl),
             "ultimo_evento": {"tipo": ev.tipo_evento, "tiempo": ev.tiempo} if ev else None}
    tokens = [estado]
    if seg is not None:
        tokens.append(f"{seg}s")
    if compl is not None:
        tokens.append(f"Compl:{texto(compl)}%")
    return datos, _pantallas(tokens)


CONSULTAS = {"1": _t1, "2": _t2, "3": _t3, "4": _t4, "5": _t5, "6": _t6, "7": _t7}


@router.get("/{tecla}")
def consultar(tecla: str, dispositivo_id: int,
              formato: Literal["json", "lcd"] = "json", db: Session = Depends(get_db)):
    """formato=lcd -> texto plano para el ESP32: 2 líneas por pantalla, separadas por \\n."""
    opcion = db.query(OpcionMenu).filter(OpcionMenu.tecla == tecla).first()
    if opcion is None or tecla not in CONSULTAS:
        raise HTTPException(404, detail="Tecla sin consulta asociada (válidas: 1 a 7)")
    if db.get(Dispositivo, dispositivo_id) is None:
        raise HTTPException(404, detail="Dispositivo no registrado")

    datos, pantallas = CONSULTAS[tecla](db, dispositivo_id)
    pantallas = [[linea[:16] for linea in pantalla] for pantalla in pantallas]   # el LCD tiene 16 columnas
    lineas = [linea for pantalla in pantallas for linea in pantalla if linea]
    db.add(ConsultaMenu(dispositivo_id=dispositivo_id, opcion_id=opcion.id,
                        resultado=(" | ".join(lineas) or "sin datos")[:100]))
    db.commit()
    if formato == "lcd":
        cuerpo = "\n".join(linea for pantalla in pantallas for linea in pantalla)
        cuerpo = unicodedata.normalize("NFKD", cuerpo).encode("ascii", "ignore").decode("ascii")
        return PlainTextResponse(cuerpo)   # el LCD HD44780 solo muestra ASCII
    return {"tecla": tecla, "descripcion": opcion.descripcion,
            "concepto_analitica": opcion.concepto_analitica, "dispositivo_id": dispositivo_id,
            "generado_en": datetime.now(timezone.utc), "datos": datos,
            "pantallas": pantallas}


@router.post("/registro", status_code=201)
def registrar_tecla(payload: RegistroTecla, db: Session = Depends(get_db)):
    """
    El ESP32 registra aquí las teclas que resuelve él solo (1 = valores actuales,
    7 = estado de conexión). Las teclas 2 a 6 las registra la propia API al atender
    el GET, así que no se duplican.
    """
    ahora = datetime.now(timezone.utc)
    tiempo = payload.tiempo or ahora
    if tiempo.tzinfo is None:
        tiempo = tiempo.replace(tzinfo=timezone.utc)
    if tiempo > ahora + MAX_ADELANTO or tiempo < ahora - MAX_ANTIGUEDAD:
        raise HTTPException(422, detail="'tiempo' fuera de rango aceptable")
    if db.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(404, detail="Dispositivo no registrado")
    opcion = db.query(OpcionMenu).filter(OpcionMenu.tecla == payload.tecla).first()
    if opcion is None:
        raise HTTPException(404, detail="La tecla no existe en opciones_menu")

    registro = ConsultaMenu(dispositivo_id=payload.dispositivo_id, opcion_id=opcion.id,
                            resultado=payload.resultado, tiempo=tiempo)
    db.add(registro)
    db.commit()
    return {"id": registro.id}