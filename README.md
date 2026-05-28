# Sistema de Asistencia Facial - Backend API

Backend Flask para reconocimiento facial con **InsightFace** (embeddings 512-d) e integración MySQL. API REST pura para consumo desde frontend React.

## 🚀 Inicio Rápido (Local)

### 1. Instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux
pip install -r requirements.txt
```

### 2. Configurar MySQL

- Crear base de datos `bdiayccontrolasistencia`
- Las tablas se manejan manualmente (ver `SQL_INIT.sql`)
- Configurar credenciales en `.env`:

```env
DB_HOST=localhost
DB_USER=usrpavas
DB_PASSWORD=tu_password
DB_NAME=bdiayccontrolasistencia
```

### 3. Ejecutar aplicación

```bash
python app.py
```

API disponible en: `http://localhost:5048`

---

## 🌐 Despliegue en VPS (Hostinger)

### 1. Preparar el Entorno

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y
```

### 2. Clonar repositorio

```bash
cd /var/www/pavastecnologia.com/html
git clone https://github.com/tu-usuario/reconocimiento_facial_iayc.git
cd reconocimiento_facial_iayc
```

### 3. Entorno virtual y dependencias

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install opencv-contrib-python==4.10.0.84
pip install flask flask-cors gunicorn mysql-connector-python numpy python-dotenv
pip install insightface
```

### 4. Gestionar con PM2

```bash
pm2 start process.json
pm2 save
pm2 startup
```

### 5. Proxy inverso Nginx

```nginx
location /asistenciafac-api/ {
    proxy_pass http://127.0.0.1:5048/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_redirect off;
}
```

```bash
sudo nginx -t && sudo systemctl restart nginx
```

---

## 🔗 API Endpoints

| Método   | Ruta                                | Descripción                                      |
| -------- | ----------------------------------- | ------------------------------------------------ |
| `POST`   | `/api/registrar/frame`              | Captura frame (base64) para entrenamiento        |
| `POST`   | `/api/registrar/finalizar`          | Finaliza captura y registra en BD                |
| `POST`   | `/api/entrenar`                     | Extrae embeddings con InsightFace y guarda en BD |
| `POST`   | `/api/reconocer`                    | Reconoce rostro por similitud coseno             |
| `POST`   | `/api/asistencia`                   | Registra asistencia del empleado reconocido      |
| `GET`    | `/api/usuarios`                     | Lista usuarios con estado de entrenamiento       |
| `GET`    | `/api/asistencias`                  | Últimas 50 asistencias                           |
| `POST`   | `/api/entrenar-global`              | Consulta estado global de embeddings             |
| `GET`    | `/api/entrenamiento/estado`         | Estado del sistema                               |
| `DELETE` | `/api/entrenamiento/eliminar`       | Elimina entrenamiento de un usuario              |
| `POST`   | `/api/entrenamiento/reset-completo` | Reset total del sistema                          |

---

## 🛡️ Características

- **InsightFace (buffalo_l)**: embeddings 512-d, precisión ~99%
- **Cosine similarity**: matching robusto vs LBPH
- **Embeddings en MySQL**: sin archivos .yml ni cache JSON
- **Anti-spoofing**: detección de liveness por Laplacian
- **Migración incluida**: `python -m services.migration` convierte datos LBPH antiguos

## 🛠️ Requisitos

- Python 3.9+
- MySQL 8.0+
- OpenCV Contrib (opencv-contrib-python)
- InsightFace / ONNX Runtime
