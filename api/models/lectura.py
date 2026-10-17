"""
models/lectura.py
Hypertable de TimescaleDB. Se crea en el script SQL (create_hypertable), NO desde
SQLAlchemy: por eso main.py nunca llama a Base.metadata.create_all().

Es la única tabla sin columna id: TimescaleDB exige que toda llave única incluya la
columna de tiempo, así que la llave primaria es compuesta y coincide con el SQL:
(dispositivo_id, variable_id, tiempo). Esa misma llave evita duplicados en los
reintentos (INSERT ... ON CONFLICT DO NOTHING).
  tiempo      -> hora de la MEDICIÓN
  recibido_en -> hora de llegada a la base (la pone la BD)
  valor       -> NUMERIC(5,1): siempre con un decimal
"""
from sqlalchemy import Column, Integer, Numeric, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class Lectura(Base):
    __tablename__ = "lecturas"

    dispositivo_id = Column(Integer, ForeignKey("dispositivos.id"), primary_key=True, nullable=False)
    variable_id = Column(Integer, ForeignKey("variables.id"), primary_key=True, nullable=False)
    tiempo = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    valor = Column(Numeric(5, 1, asdecimal=False), nullable=False)
    recibido_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispositivo = relationship("Dispositivo", back_populates="lecturas")
    variable = relationship("Variable", back_populates="lecturas")