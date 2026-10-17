from sqlalchemy import Column, BigInteger, Integer, Numeric, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Alerta(Base):
    """Historial de alertas con estado. Una alerta = un episodio fuera de umbral."""
    __tablename__ = "alertas"

    id = Column(BigInteger, primary_key=True)
    tiempo = Column(DateTime(timezone=True), nullable=False)
    dispositivo_id = Column(Integer, ForeignKey("dispositivos.id"), nullable=False)
    variable_id = Column(Integer, ForeignKey("variables.id"), nullable=False)
    umbral_id = Column(Integer, ForeignKey("umbrales_alerta.id"), nullable=False)
    valor = Column(Numeric(5, 1, asdecimal=False), nullable=False)
    tipo = Column(String(10), nullable=False)          # 'BAJO' | 'ALTO'
    activa = Column(Boolean, nullable=False, default=True, server_default="true")
    resuelta_en = Column(DateTime(timezone=True))

    dispositivo = relationship("Dispositivo", back_populates="alertas")
    variable = relationship("Variable", back_populates="alertas")
    umbral = relationship("UmbralAlerta", back_populates="alertas")