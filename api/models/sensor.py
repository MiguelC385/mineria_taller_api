from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class Sensor(Base):
    __tablename__ = "sensores"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), nullable=False, unique=True)
    descripcion = Column(String(200))

    dispositivos = relationship("DispositivoSensor", back_populates="sensor")
    variables = relationship("Variable", back_populates="sensor")
