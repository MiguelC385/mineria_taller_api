from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class EventoSistema(Base):
    __tablename__ = "eventos_sistema"

    id = Column(Integer, primary_key=True, index=True)
    dispositivo_id = Column(Integer, ForeignKey("dispositivos.id"), nullable=False)
    tipo_evento = Column(String(50), nullable=False)
    mensaje = Column(String(300))
    tiempo = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispositivo = relationship("Dispositivo", back_populates="eventos")
