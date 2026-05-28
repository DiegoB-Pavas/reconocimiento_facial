import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME')
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Data')
MODELS_DIR = os.path.join(BASE_DIR, 'modelos')

TOTAL_FOTOS = 30

FLASK_CONFIG = {
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'tu_clave_secreta_aqui'),
    'DEBUG': os.environ.get('FLASK_DEBUG', '0') == '1'
}

SERVER_CONFIG = {
    'host': '0.0.0.0',
    'port': int(os.environ.get('APP_PORT', 5048)),
    'debug': True
}

# InsightFace / embedding configuration
SIMILARITY_THRESHOLD = 0.70
INSIGHTFACE_MODEL_NAME = 'buffalo_l'
EMBEDDING_DIM = 512
MIN_DETECTION_SCORE = 0.3

# Anti-spoofing (DeePixBiS) configuration
ANTISPOOF_MODEL_DIR = os.path.join(MODELS_DIR, 'deeppixbis')
ANTISPOOF_REAL_THRESHOLD = float(os.environ.get('ANTISPOOF_REAL_THRESHOLD', 0.5))
