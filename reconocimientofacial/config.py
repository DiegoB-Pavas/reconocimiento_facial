# config.py - Configuración de la aplicación
import os

from dotenv import load_dotenv

# Carga las variables de entorno desde un archivo .env si existe
load_dotenv()

# Configuración MySQL (estrictamente por variables de entorno)
MYSQL_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME')
}

# Rutas de directorios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Data')
MODELS_DIR = os.path.join(BASE_DIR, 'modelos')

# Configuración del sistema
TOTAL_FOTOS = 300  # Número máximo de fotos por usuario

# Configuración Flask
FLASK_CONFIG = {
    'SECRET_KEY': 'tu_clave_secreta_aqui',  # Cambiar en producción
    'DEBUG': True
}

# Configuración del servidor
SERVER_CONFIG = {
    'host': '0.0.0.0',
    'port': 5048,
    'debug': True
}