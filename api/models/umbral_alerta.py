from sqlalchemy import Column, Integer, Numeric, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class UmbralAlerta(Base):
    """Rango ESPERADO: fuera de él el dato se guarda pero genera una alerta."""
    __tablename__ = "umbrales_alerta"

    id = Column(Integer, primary_key=True, index=True)
    variable_id = Column(Integer, ForeignKey("variables.id"), nullable=False)
    umbral_min = Column(Numeric(5, 1, asdecimal=False), nullable=False)
    umbral_max = Column(Numeric(5, 1, asdecimal=False), nullable=False)
    descripcion = Column(String(200))
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    variable = relationship("Variable", back_populates="umbrales")
    alertas = relationship("Alerta", back_populates="umbral")