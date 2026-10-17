import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()  # lee el archivo .env en local; en Render no existe y no pasa nada

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta la variable de entorno DATABASE_URL (ver .env.example)")

# Fuerza el driver psycopg2 aunque la URL venga como postgres:// o postgresql://
for prefijo in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(prefijo):
        DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len(prefijo):]
        break

# pool_pre_ping: Neon suspende el compute por inactividad y cierra conexiones;
# esto verifica la conexión antes de usarla y evita errores tras una pausa.
# pool_recycle: renueva conexiones viejas cada 5 minutos.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: una sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
