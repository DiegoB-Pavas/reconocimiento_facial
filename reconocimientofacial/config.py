# config.py - Configuración de la aplicación
import os

# Configuración MySQL
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
    'database': 'bdcsurhorario'
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