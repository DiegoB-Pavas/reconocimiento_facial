# Plan: Migrar de db.json a MySQL con estructura de entrenamientos

**TL;DR:** Convertir Flask de `db.json` → MySQL (`bdcsurhorario`). Crearemos tabla `entrenamientos_faciales` (nueva) + usar `usuarios` (existente). El backend usará `usuario_id` como identificador en lugar de nombre, permitiendo histórico de entrenamientos y estado (pendiente → entrenado → fallido).

---

## Steps

### Fase 1: Setup (Dependencias + Configuración)

1. **Instalar driver MySQL**
   - `pip install mysql-connector-python`
   - Verificar que Flask siga funcionando

2. **Crear archivo de configuración** (`config.py`)
   - Almacenar credenciales MySQL (host: localhost, usuario: root, contraseña: 1234, BD: bdcsurhorario)
   - Variables globales como TOTAL_FOTOS, rutas de directorios

3. **Crear archivo de conexión DB** (`database.py`)
   - Función `get_connection()` para establecer conexión a MySQL
   - Función `init_db()` para crear tabla `entrenamientos_faciales` si no existe
   - Funciones helper para CRUD básico (insert, select, update)

### Fase 2: Base de datos

4. **Ejecutar script SQL** para crear tabla `entrenamientos_faciales`
   ```sql
   CREATE TABLE tbl_facial_training (
      fac_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
      fk_pem_id CHAR(36) NOT NULL,
      fac_training_date DATETIME,
      fac_num_photos_captured INT,
      fac_state ENUM('pendiente', 'entrenado', 'fallido'),
      fac_ruta_modelo VARCHAR(255),
      fac_precision FLOAT,
      fac_created_by CHAR(36),
      fac_updated_by CHAR(36),
      fac_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      fac_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      FOREIGN KEY (fk_pem_id) REFERENCES tbl_pay_employees(pem_id) ON DELETE CASCADE
   );
   CREATE INDEX idx_pem_id ON tbl_facial_training(fk_pem_id);
   ```

### Fase 3: Refactorizar endpoints

5. **Reemplazar funciones de BD** en `app.py`
   - Eliminar `load_db()` y `save_db()` (que usan JSON)
   - Crear `get_usuario_mysql(usuario_id)`, `insert_entrenamiento()`, `update_entrenamiento()`
   - Crear `get_all_usuarios()`, `get_asistencias()` desde MySQL

6. **Actualizar endpoint `/api/registrar/frame`**
   - Cambiar: Crear carpeta por `usuario_id` (no por nombre)
   - Cambiar: `Data/usuario_id/img_0.jpg` en lugar de `Data/Diego_Buitrago/img_0.jpg`
   - Validar que usuario exista en MySQL antes de guardar foto
   - Retornar `usuario_id` en response

7. **Actualizar endpoint `/api/registrar/finalizar`**
   - Buscar usuario en MySQL por ID (no por nombre)
   - Insertar/actualizar registro en `entrenamientos_faciales` con estado='pendiente'
   - Guardar `fecha_entrenamiento`

8. **Actualizar endpoint `/api/entrenar`**
   - Leer fotos desde directorios de `usuario_id` (en lugar de nombres)
   - **Crear modelo individual por usuario:** `modelos/usuario_{usuario_id}_modelo.yml`
   - En lugar de guardar `labels.json`, guardar `usuario_id → nombre` en BD por entrenamiento
   - Actualizar `tbl_facial_training` con estado='entrenado', ruta_modelo, precision
   - **Eliminar carpeta de fotos después del entrenamiento exitoso** para optimizar espacio
   - Retornar ID de entrenamiento en response

9. **Actualizar endpoint `/api/reconocer`**
   - **Cargar TODOS los modelos entrenados:** Query BD por `fac_state = 'entrenado'`
   - Para cada modelo activo, cargar desde `fac_ruta_modelo` y probar reconocimiento
   - Usar `usuario_id` en lugar de nombre como identificador interno
   - Retornar `usuario_id + nombre` del modelo con mejor coincidencia

10. **Actualizar endpoint `/api/asistencia`**
    - Buscar usuario por `usuario_id` (no por nombre)
    - Validar que usuario tenga entrenamiento activo (estado='entrenado')
    - Guardar asistencia en tabla MySQL (en lugar de JSON)

11. **Actualizar endpoints `/api/usuarios` y `/api/asistencias`**
    - Leer de MySQL (tabla usuarios y asistencias) en lugar de db.json
    - Retornar estructura esperada por React

### Fase 4: Integración React

12. **Agregar soporte CORS**
    - `pip install flask-cors`
    - Configurar `CORS(app)` en app.py
    - Agregar `@cross_origin()` en endpoints API

13. **Documentar API**
    - Crear `API_DOCS.md` con endpoints, parámetros, respuestas

---

## Relevant files

- [app.py](reconocimientofacial/app.py) — Refactorizar a MySQL
- **config.py** (crear nuevo) — Credenciales MySQL
- **database.py** (crear nuevo) — Funciones de conexión y helpers
- **SQL_INIT.sql** (crear nuevo) — Script para crear tabla
- **requirements.txt** (crear/actualizar) — `mysql-connector-python`, `flask-cors`

---

## Verification Checklist

- [ ] `pip install -r requirements.txt` funciona
- [ ] `import mysql.connector` funciona en Python
- [ ] Tabla `tbl_facial_training` existe en MySQL con FK a `usuarios`
- [ ] `GET /api/usuarios` retorna lista desde MySQL
- [ ] `POST /api/registrar/frame` crea carpeta con `usuario_id` en `Data/`
- [ ] `POST /api/entrenar` crea modelo individual `modelos/usuario_{id}_modelo.yml` y actualiza estado a 'entrenado' en BD
- [ ] `POST /api/entrenar` elimina carpeta de fotos después del entrenamiento exitoso
- [ ] `POST /api/reconocer` carga múltiples modelos y retorna el mejor match
- [ ] React puede obtener usuarios
- [ ] React puede enviar `usuario_id` para capturar fotos
- [ ] React puede iniciar entrenamiento y consultar estado

---

## Cambios clave

| Aspecto | Antes (db.json) | Después (MySQL) |
|--------|-----------------|-----------------|
| **Identificador usuario** | Nombre string | ID numérico (usuario_id) |
| **Carpeta fotos** | `Data/Diego_Buitrago/` | `Data/3/` (eliminada después del entrenamiento) |
| **Labels modelo** | `labels.json` | Tabla BD tbl_facial_training (uno por usuario) |
| **Modelo físico** | `modelo_LBPH.yml` | `modelos/usuario_{id}_modelo.yml` (uno por usuario) |
| **Historial entrenamientos** | No | Sí (registro por cada entrenamiento) |
| **Estado entrenamiento** | No explícito | ENUM (pendiente/entrenado/fallido) |
| **Base de datos** | JSON local `db.json` | MySQL `bdcsurhorario` |

---

## Decisiones arquitectónicas

- **2 tablas separadas:** `usuarios` (existente) + `tbl_facial_training` (nueva)
  - Permite historial, auditoría, renovaciones sin sobrescribir
  
- **Mantener templates HTML:** Conservar rutas `/`, `/registrar`, `/reconocer` para compatibilidad

- **Usuario_id como identificador:** Backend usa ID numérico (no nombre), más escalable y seguro

- **Estado del entrenamiento:** Campo ENUM (pendiente → entrenado → fallido) permite rastrear ciclo completo

- **Optimización de espacio:** Eliminar fotos después del entrenamiento para evitar acumulación de archivos grandes

---

## Consideraciones futuras

1. **Seguridad de credenciales:**
   - Usar variables de entorno (`.env` + `python-dotenv`) antes de deploy, no hardcodear en `config.py`

2. **Migrabilidad de datos históricos:**
   - Considerar migrar tabla `asistencias` completa a MySQL para consistencia total

3. **Modelo por usuario:**
   - Ventaja: Entrenamiento individual, mejor control de versiones
   - Consideración: En reconocimiento cargar múltiples modelos (puede ser más lento con muchos usuarios)

4. **Optimización de espacio:**
   - Eliminar carpetas de fotos después del entrenamiento exitoso
   - Evita acumulación de imágenes (350 fotos x usuario pueden ser ~50MB)
   - Si se necesita re-entrenar, React debe volver a capturar fotos

4. **Versionado de API:**
   - Considerar prefix `/api/v1/` para compatibilidad futura con React
