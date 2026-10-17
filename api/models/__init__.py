# Importar todos los modelos aquí para que SQLAlchemy resuelva las relaciones.
from .grupo import Grupo
from .integrante import Integrante
from .dispositivo import Dispositivo
from .sensor import Sensor
from .dispositivo_sensor import DispositivoSensor
from .variable import Variable
from .lectura import Lectura
from .umbral_alerta import UmbralAlerta
from .alerta import Alerta
from .evento_sistema import EventoSistema
from .opcion_menu import OpcionMenu
from .consulta_menu import ConsultaMenu
