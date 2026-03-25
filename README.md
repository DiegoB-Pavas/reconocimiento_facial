# Sistema de Asistencia Facial - Backend API

Backend Flask para reconocimiento facial de alto rendimiento con integración MySQL y soporte para React frontend. Este proyecto funciona como una API REST pura para consumo desde aplicaciones modernas.

## 🚀 Inicio Rápido (Local)

### 1. Instalar dependencias
Se recomienda usar un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar MySQL
- Crear base de datos `bdcsurhorario`.
- Ejecutar el script `SQL_INIT.sql` en phpMyAdmin o MySQL Workbench.
- Configurar credenciales en `config.py`.

### 3. Ejecutar aplicación
```bash
cd reconocimientofacial
python app.py
```
La API estará disponible en: `http://localhost:5000`

---

## 🌐 Despliegue en VPS (CentOS 9 Stream)

Para desplegar este proyecto en un VPS con **CentOS 9 Stream**, sigue estos pasos:

### 1. Preparar el Entorno
Actualiza el sistema e instala las dependencias necesarias de Python, compilación y OpenCV:
```bash
sudo dnf update -y
sudo dnf install python3 python3-devel gcc gcc-c++ -y
sudo dnf install mesa-libGL glib2 -y
```

### 2. Clonar y Configurar
Clona el repositorio en `/var/www/reconocimiento-facial`:
```bash
cd /var/www
git clone https://github.com/tu-usuario/reconocimiento_facial.git
cd reconocimiento_facial/reconocimientofacial
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### 3. Gestionar con PM2
Dado que usas **PM2**, puedes usarlo para gestionar este backend de Python. Asegúrate de tener instalado PM2 globalmente:

```bash
pm2 start process.json
```

### 4. Configurar Nginx como Proxy Inverso
En CentOS, el archivo de configuración principal suele estar en `/etc/nginx/nginx.conf` o en `/etc/nginx/conf.d/*.conf`.

Crea un archivo de configuración para tu sitio:
```bash
sudo vi /etc/nginx/conf.d/asistencia_facial.conf
```

Añade lo siguiente:
```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 10M;
}
```

Reinicia Nginx y asegúrate de que el firewall permita el tráfico HTTP/HTTPS:
```bash
sudo nginx -t
sudo systemctl restart nginx
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

> [!IMPORTANT]
> En CentOS, es posible que **SELinux** bloquee las conexiones del proxy inverso. Si recibes un error 502, ejecuta:
> `sudo setsebool -P httpd_can_network_connect 1`

---

## 🔗 API Endpoints (Para React)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/registrar/frame` | Envía frame (base64) para capturar rostro. |
| `POST` | `/api/registrar/finalizar` | Finaliza captura y crea/actualiza registro en BD. |
| `POST` | `/api/entrenar` | Procesa fotos, genera `.yml` y limpia disco. |
| `POST` | `/api/reconocer` | Prueba un frame contra todos los modelos cargados. |
| `GET`  | `/api/usuarios` | Obtiene lista de usuarios y estado de entrenamiento. |
| `GET`  | `/api/asistencias` | Obtiene historial de las últimas 50 asistencias. |

---

## 🛡️ Características Pro
- **Modelos Individuales**: Cada usuario tiene su propio archivo `.yml`, facilitando actualizaciones sin re-entrenar todo.
- **Optimización de Almacenamiento**: Las fotos se eliminan automáticamente después de un entrenamiento exitoso.
- **Detección de Vida (Liveness)**: Filtro básico para evitar suplantación con fotos impresas o pantallas.
- **Upsert Inteligente**: Si un usuario repite el entrenamiento, se actualiza su registro actual en lugar de crear duplicados.

## 🛠️ Requisitos del Sistema
- **Python 3.10+**
- **MySQL 8.0+**
- **OpenCV Contrib** (`opencv-contrib-python`)

---
Desarrollado para integración fluida con React y entornos de producción escalables.
