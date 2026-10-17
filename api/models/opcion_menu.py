from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class OpcionMenu(Base):
    __tablename__ = "opciones_menu"

    id = Column(Integer, primary_key=True, index=True)
    tecla = Column(String(2), nullable=False, unique=True)
    descripcion = Column(String(100), nullable=False)
    concepto_analitica = Column(String(150), nullable=False)

    consultas = relationship("ConsultaMenu", back_populates="opcion")