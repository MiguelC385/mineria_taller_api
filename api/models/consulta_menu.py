from sqlalchemy import Column, BigInteger, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class ConsultaMenu(Base):
    """Bitácora de teclas presionadas (la API la llena al atender cada consulta)."""
    __tablename__ = "consultas_menu"

    id = Column(BigInteger, primary_key=True)
    dispositivo_id = Column(Integer, ForeignKey("dispositivos.id"), nullable=False)
    opcion_id = Column(Integer, ForeignKey("opciones_menu.id"), nullable=False)
    resultado = Column(String(100))
    tiempo = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispositivo = relationship("Dispositivo", back_populates="consultas")
    opcion = relationship("OpcionMenu", back_populates="consultas")