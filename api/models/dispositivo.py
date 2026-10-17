from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=False)
    nombre_alias = Column(String(100), nullable=False)
    ubicacion = Column(String(150))
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    grupo = relationship("Grupo", back_populates="dispositivos")
    sensores = relationship("DispositivoSensor", back_populates="dispositivo")
    lecturas = relationship("Lectura", back_populates="dispositivo")
    alertas = relationship("Alerta", back_populates="dispositivo")
    eventos = relationship("EventoSistema", back_populates="dispositivo")
    consultas = relationship("ConsultaMenu", back_populates="dispositivo")
