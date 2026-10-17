from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class Variable(Base):
    """Rango FÍSICO válido: fuera de [valor_min, valor_max] la API rechaza el dato."""
    __tablename__ = "variables"
    __table_args__ = (UniqueConstraint("sensor_id", "nombre"),)

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensores.id"), nullable=False)
    nombre = Column(String(50), nullable=False)
    unidad = Column(String(20), nullable=False)
    valor_min = Column(Numeric(5, 1, asdecimal=False), nullable=False)
    valor_max = Column(Numeric(5, 1, asdecimal=False), nullable=False)

    sensor = relationship("Sensor", back_populates="variables")
    lecturas = relationship("Lectura", back_populates="variable")
    umbrales = relationship("UmbralAlerta", back_populates="variable")
    alertas = relationship("Alerta", back_populates="variable")