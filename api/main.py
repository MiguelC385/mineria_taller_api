"""
main.py
Arranque local : uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Arranque Render: uvicorn main:app --host 0.0.0.0 --port $PORT
"""
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routers import lecturas, consultas, eventos

app = FastAPI(
    title="API IoT - Series temporales",
    description="Recibe lecturas de sensores y sirve las consultas del menú del teclado.",
    version="2.1.0",
)

app.include_router(lecturas.router)
app.include_router(consultas.router)
app.include_router(eventos.router)


@app.get("/health", tags=["Sistema"])
def health(db: Session = Depends(get_db)):
    """Verifica que la API y la base de datos respondan (útil como health check en Render)."""
    db.execute(text("SELECT 1"))
    return {"estado": "ok"}
