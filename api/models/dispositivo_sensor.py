from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class DispositivoSensor(Base):
    __tablename__ = "dispositivo_sensor"
    __table_args__ = (UniqueConstraint("dispositivo_id", "sensor_id"),)

    id = Column(Integer, primary_key=True, index=True)
    dispositivo_id = Column(Integer, ForeignKey("dispositivos.id"), nullable=False)
    sensor_id = Column(Integer, ForeignKey("sensores.id"), nullable=False)
    fecha_instalacion = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dispositivo = relationship("Dispositivo", back_populates="sensores")
    sensor = relationship("Sensor", back_populates="dispositivos")
