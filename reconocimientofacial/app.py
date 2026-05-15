from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import cv2
import numpy as np
import os
import json
import base64
import sys
from datetime import datetime
import shutil  # Para eliminar carpetas

# Importar configuración y base de datos
from config import MYSQL_CONFIG, BASE_DIR, DATA_DIR, MODELS_DIR, TOTAL_FOTOS, FLASK_CONFIG, SERVER_CONFIG
from database import (
    get_connection, init_db, get_empleado_by_id, get_all_empleados,
    insert_entrenamiento, update_entrenamiento, get_entrenamientos_activos,
    get_entrenamiento_by_empleado, get_asistencias, save_asistencia,
    delete_entrenamiento, get_entrenamiento_by_id, get_empleados_pendientes_entrenamiento
)

app = Flask(__name__)

# Configurar Flask
app.config.update(FLASK_CONFIG)

# Configurar CORS para React
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"],  # URLs de React
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Inicializar base de datos
if not init_db():
    print("ERROR: No se pudo conectar a la base de datos MySQL")
    exit(1)

face_cascade = cv2.CascadeClassifier(
    os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
eye_cascade = cv2.CascadeClassifier(
    os.path.join(cv2.data.haarcascades, 'haarcascade_eye.xml'))


def decode_image(b64):
    if ',' in b64:
        b64 = b64.split(',')[1]
    data = base64.b64decode(b64)
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def check_liveness(face_gray):
    """Anti-spoofing basico: analisis de textura con Laplacian.
    Fotos impresas o en pantalla tienden a tener varianza muy baja."""
    lap_var = cv2.Laplacian(face_gray, cv2.CV_64F).var()
    return lap_var > 8, round(lap_var, 1)


# ── API ───────────────────────────────────────────────────────────

@app.route('/api/registrar/frame', methods=['POST'])
@cross_origin()
def api_registrar_frame():
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400

    # Verificar que el empleado existe en MySQL
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404

    frame = decode_image(data['image'])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return jsonify({'status': 'no_face'})
    if len(faces) > 1:
        return jsonify({'status': 'multiple'})

    x, y, w, h = faces[0]
    face_gray = gray[y:y+h, x:x+w]

    is_real, score = check_liveness(face_gray)
    if not is_real:
        return jsonify({'status': 'fake', 'score': score})

    # Crear carpeta por empleado_id
    folder = os.path.join(DATA_DIR, empleado_id)
    os.makedirs(folder, exist_ok=True)
    count = len([f for f in os.listdir(folder) if f.endswith('.jpg')])

    if count >= TOTAL_FOTOS:
        return jsonify({'status': 'complete', 'count': count})

    face_resized = cv2.resize(frame[y:y+h, x:x+w], (160, 160),
                              interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(os.path.join(folder, f'img_{count}.jpg'), face_resized)

    return jsonify({
        'status': 'ok',
        'count': count + 1,
        'total': TOTAL_FOTOS,
        'face': {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)},
        'empleado_id': empleado_id
    })


@app.route('/api/registrar/finalizar', methods=['POST'])
@cross_origin()
def api_registrar_fin():
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400

    # Verificar que el empleado existe
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404

    folder = os.path.join(DATA_DIR, empleado_id)
    if not os.path.exists(folder):
        return jsonify({'error': 'Sin datos de fotos'}), 400

    count = len([f for f in os.listdir(folder) if f.endswith('.jpg')])
    if count == 0:
        return jsonify({'error': 'No hay fotos capturadas'}), 400

    # Insertar registro de entrenamiento en MySQL
    entrenamiento_id = insert_entrenamiento(empleado_id, count, empleado_id)
    if not entrenamiento_id:
        return jsonify({'error': 'Error al guardar en base de datos'}), 500

    return jsonify({
        'status': 'ok',
        'count': count,
        'entrenamiento_id': entrenamiento_id,
        'empleado_id': empleado_id
    })


@app.route('/api/entrenar', methods=['POST'])
@cross_origin()
def api_entrenar():
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400

    # Verificar que el empleado existe
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404

    # Verificar que hay un entrenamiento pendiente
    entrenamiento = get_entrenamiento_by_empleado(empleado_id)
    if not entrenamiento or entrenamiento['fac_state'] != 'pendiente':
        return jsonify({'error': 'No hay entrenamiento pendiente para este empleado'}), 400

    # Verificar carpeta de fotos
    folder = os.path.join(DATA_DIR, empleado_id)
    if not os.path.exists(folder):
        return jsonify({'error': 'No hay fotos para entrenar'}), 400

    # Leer fotos del usuario
    faces = []
    for img_file in os.listdir(folder):
        if not img_file.endswith('.jpg'):
            continue
        img_path = os.path.join(folder, img_file)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            faces.append(cv2.resize(img, (160, 160)))

    if not faces:
        return jsonify({'error': 'No se encontraron imágenes válidas'}), 400

    # Entrenar modelo individual
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array([0] * len(faces)))  # Solo un usuario, ID=0

    # Guardar modelo individual
    os.makedirs(MODELS_DIR, exist_ok=True)
    modelo_path = os.path.join(MODELS_DIR, f'empleado_{empleado_id}_modelo.yml')
    print(f"[DEBUG] Guardando modelo en: {modelo_path}", file=sys.stderr)
    print(f"[DEBUG] MODELS_DIR es: {MODELS_DIR}", file=sys.stderr)
    recognizer.write(modelo_path)

    # Calcular precisión básica (opcional - por ahora usamos 0.85 como ejemplo)
    precision = 0.85  # TODO: Implementar validación cruzada real

    # Actualizar BD
    updates = {
        'fac_state': 'entrenado',
        'fac_ruta_modelo': modelo_path,
        'fac_precision': precision
    }
    if not update_entrenamiento(entrenamiento['fac_id'], updates, empleado_id):
        return jsonify({'error': 'Error al actualizar base de datos'}), 500

    # Eliminar carpeta de fotos para optimizar espacio
    try:
        shutil.rmtree(folder)
        print(f"Carpeta eliminada: {folder}")
    except Exception as e:
        print(f"Error eliminando carpeta: {e}")
    
    cache_data = cargar_rostros_cache()
    cache_data[empleado_id] = {
        'rostros_base64': [],
        'empleado_nombre': empleado['pem_full_name']
    }
    import base64 as b64
    for face in faces:
        _, buffer = cv2.imencode('.jpg', face)
        cache_data[empleado_id]['rostros_base64'].append(b64.b64encode(buffer).decode('utf-8'))
    guardar_rostros_cache_to_disk(cache_data)
    
    global_result = reentrenar_modelo_global()
    
    if global_result:
        print(f"[DEBUG] Modelo global reentrenado: {global_result}", file=sys.stderr)
    else:
        print(f"[DEBUG] No se pudo reentrenar modelo global", file=sys.stderr)
    
    response = {
        'status': 'ok',
        'empleado_id': empleado_id,
        'entrenamiento_id': entrenamiento['fac_id'],
        'imagenes_entrenadas': len(faces),
        'precision': precision,
        'modelo_path': modelo_path
    }
    if global_result:
        response['modelo_global'] = global_result
    
    return jsonify(response)


rostros_cache_path = os.path.join(MODELS_DIR, 'rostros_cache.json')

def guardar_rostros_cache():
    """Guarda el cache de rostros en disco"""
    cache_data = {}
    if os.path.exists(rostros_cache_path):
        with open(rostros_cache_path, 'r') as f:
            cache_data = json.load(f)
    return cache_data

def cargar_rostros_cache():
    """Carga el cache de rostros desde disco"""
    if os.path.exists(rostros_cache_path):
        with open(rostros_cache_path, 'r') as f:
            return json.load(f)
    return {}

def guardar_rostros_cache_to_disk(cache_data):
    """Guarda cache de rostros a disco"""
    with open(rostros_cache_path, 'w') as f:
        json.dump(cache_data, f, indent=2)


def reentrenar_modelo_global():
    """Reentrena el modelo global con todos los rostros del cache"""
    import base64 as b64
    
    print(f"[DEBUG] reentrenar_modelo_global: MODELS_DIR={MODELS_DIR}", file=sys.stderr)
    
    cache_data = cargar_rostros_cache()
    print(f"[DEBUG] Cache encontrado: {list(cache_data.keys())}", file=sys.stderr)
    
    global_model_path = os.path.join(MODELS_DIR, 'modelo_global.yml')
    labels_json_path = os.path.join(MODELS_DIR, 'labels.json')
    
    if not cache_data:
        print("[DEBUG] Cache vacío, eliminando modelo global existente", file=sys.stderr)
        if os.path.exists(global_model_path):
            os.remove(global_model_path)
        if os.path.exists(labels_json_path):
            os.remove(labels_json_path)
        return None
    
    all_faces = []
    all_labels = []
    label_to_empleado = {}
    
    for idx, (empleado_id, data) in enumerate(cache_data.items()):
        num_rostros = len(data.get('rostros_base64', []))
        print(f"[DEBUG] Procesando empleado {empleado_id}: {num_rostros} rostros", file=sys.stderr)
        for rostro_b64 in data.get('rostros_base64', []):
            img_data = b64.b64decode(rostro_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                all_faces.append(cv2.resize(img, (160, 160)))
                all_labels.append(idx)
        
        label_to_empleado[idx] = {
            'empleado_id': empleado_id,
            'nombre': data.get('empleado_nombre', '')
        }
    
    print(f"[DEBUG] Total rostros cargados: {len(all_faces)}, labels: {len(set(all_labels))}", file=sys.stderr)
    
    if not all_faces:
        print("[DEBUG] No hay rostros válidos, no se crea modelo global", file=sys.stderr)
        return None
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(all_faces, np.array(all_labels))
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    global_model_path = os.path.join(MODELS_DIR, 'modelo_global.yml')
    print(f"[DEBUG] Guardando modelo global en: {global_model_path}", file=sys.stderr)
    recognizer.write(global_model_path)
    
    labels_json_path = os.path.join(MODELS_DIR, 'labels.json')
    with open(labels_json_path, 'w') as f:
        json.dump(label_to_empleado, f)
    
    print(f"[DEBUG] Modelo global creado exitosamente", file=sys.stderr)
    
    return {
        'empleados_entrenados': len(label_to_empleado),
        'total_imagenes': len(all_faces),
        'modelo_path': global_model_path
    }


@app.route('/api/entrenar-individual', methods=['POST'])
@cross_origin()
def api_entrenar_individual():
    """Entrena modelo individual y guarda rostros en cache para uso futuro del modelo global"""
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400
    
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    
    folder = os.path.join(DATA_DIR, empleado_id)
    if not os.path.exists(folder):
        return jsonify({'error': 'No hay fotos para entrenar'}), 400
    
    faces = []
    for img_file in os.listdir(folder):
        if not img_file.endswith('.jpg'):
            continue
        img = cv2.imread(os.path.join(folder, img_file), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            faces.append(cv2.resize(img, (160, 160)))
    
    if not faces:
        return jsonify({'error': 'No se encontraron imágenes válidas'}), 400
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array([0] * len(faces)))
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    modelo_path = os.path.join(MODELS_DIR, f'empleado_{empleado_id}_modelo.yml')
    recognizer.write(modelo_path)
    
    cache_data = cargar_rostros_cache()
    cache_data[empleado_id] = {
        'rostros_base64': [],
        'empleado_nombre': empleado['pem_full_name']
    }
    
    import base64 as b64
    for face in faces:
        _, buffer = cv2.imencode('.jpg', face)
        cache_data[empleado_id]['rostros_base64'].append(b64.b64encode(buffer).decode('utf-8'))
    
    guardar_rostros_cache_to_disk(cache_data)
    
    entrenamiento = get_entrenamiento_by_empleado(empleado_id)
    if entrenamiento:
        update_entrenamiento(entrenamiento['fac_id'], {
            'fac_state': 'entrenado',
            'fac_ruta_modelo': modelo_path,
            'fac_precision': 0.85
        }, empleado_id)
    
    shutil.rmtree(folder)
    
    print(f"[DEBUG] Carpeta {folder} eliminada, iniciando reentrenamiento global...", file=sys.stderr)
    global_result = reentrenar_modelo_global()
    
    response = {
        'status': 'ok',
        'empleado_id': empleado_id,
        'rostros_guardados_cache': len(faces),
        'modelo_path': modelo_path
    }
    
    if global_result:
        response['modelo_global'] = global_result
    
    return jsonify(response)


@app.route('/api/entrenar-global', methods=['POST'])
@cross_origin()
def api_entrenar_global():
    """Entrena/reentrena modelo global combinando cache de rostros de todos los usuarios"""
    cache_data = cargar_rostros_cache()
    
    if not cache_data:
        return jsonify({'error': 'No hay rostros en cache para entrenar'}), 400
    
    import base64 as b64
    
    all_faces = []
    all_labels = []
    label_to_empleado = {}
    
    for idx, (empleado_id, data) in enumerate(cache_data.items()):
        for rostro_b64 in data['rostros_base64']:
            img_data = b64.b64decode(rostro_b64)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                all_faces.append(cv2.resize(img, (160, 160)))
                all_labels.append(idx)
        
        label_to_empleado[idx] = {
            'empleado_id': empleado_id,
            'nombre': data.get('empleado_nombre', '')
        }
    
    if not all_faces:
        return jsonify({'error': 'No se pudieron decodificar rostros del cache'}), 400
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(all_faces, np.array(all_labels))
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    global_model_path = os.path.join(MODELS_DIR, 'modelo_global.yml')
    recognizer.write(global_model_path)
    
    labels_json_path = os.path.join(MODELS_DIR, 'labels.json')
    with open(labels_json_path, 'w') as f:
        json.dump(label_to_empleado, f)
    
    return jsonify({
        'status': 'ok',
        'empleados_entrenados': len(label_to_empleado),
        'total_imagenes': len(all_faces),
        'modelo_path': global_model_path
    })


@app.route('/api/reconocer', methods=['POST'])
@cross_origin()
def api_reconocer():
    """Reconocimiento facial usando modelo global único con labels únicos"""
    frame = decode_image(request.json['image'])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    labels_json_path = os.path.join(MODELS_DIR, 'labels.json')
    global_model_path = os.path.join(MODELS_DIR, 'modelo_global.yml')
    
    print(f"[DEBUG] api_reconocer: global_model_path={global_model_path}", file=sys.stderr)
    print(f"[DEBUG] api_reconocer: labels_json_path={labels_json_path}", file=sys.stderr)
    
    if not os.path.exists(global_model_path):
        print(f"[DEBUG] api_reconocer: Modelo global no existe", file=sys.stderr)
        return jsonify({'error': 'No hay modelo global entrenado'}), 400
    
    with open(labels_json_path, 'r') as f:
        label_to_empleado = json.load(f)
    print(f"[DEBUG] api_reconocer: labels={label_to_empleado}", file=sys.stderr)
    
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(global_model_path)
    
    results = []
    for (x, y, w, h) in faces:
        face_roi = cv2.resize(gray[y:y+h, x:x+w], (160, 160))

        is_real, _ = check_liveness(face_roi)
        if not is_real:
            results.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'empleado_id': None,
                'nombre': 'FOTO DETECTADA',
                'confianza': 0,
                'valido': False
            })
            continue

        label_id, confidence = recognizer.predict(face_roi)
        
        # Convertir confidence a porcentaje (menor confidence = mayor confianza)
        confianza_pct = max(0, round(100 - confidence))
        
        # Umbral: confianza >= 50% y confidence < 65
        valido = confidence < 80 and confianza_pct >= 20
        
        if valido and str(label_id) in label_to_empleado:
            emp_data = label_to_empleado[str(label_id)]
            results.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'empleado_id': emp_data['empleado_id'],
                'nombre': emp_data['nombre'],
                'confianza': confianza_pct,
                'valido': True
            })
        else:
            results.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'empleado_id': None,
                'nombre': 'Desconocido',
                'confianza': confianza_pct,
                'valido': False
            })

    return jsonify({'faces': results})


@app.route('/api/asistencia', methods=['POST'])
@cross_origin()
def api_asistencia():
    empleado_id = request.json.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400

    # Verificar que el empleado existe y tiene entrenamiento activo
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404

    entrenamiento = get_entrenamiento_by_empleado(empleado_id)
    if not entrenamiento or entrenamiento['fac_state'] != 'entrenado':
        return jsonify({'error': 'Empleado no tiene entrenamiento activo'}), 400

    now = datetime.now()

    # Verificar duplicados en ventana de 5 minutos
    asistencias = get_asistencias(50)  # Últimas 50 asistencias
    for a in reversed(asistencias):
        if a.get('empleado_id') == empleado_id:
            # Si hay timestamp, verificar tiempo
            if 'timestamp' in a:
                try:
                    ts = datetime.fromisoformat(a['timestamp'])
                    if (now - ts).total_seconds() < 300:
                        return jsonify({
                            'status': 'duplicate',
                            'message': f'{empleado["pem_full_name"]} ya registrado hace poco'
                        })
                except:
                    pass
            break

    # Registrar asistencia
    asistencia = {
        'empleado_id': empleado_id,
        'usuario': empleado['pem_full_name'],
        'timestamp': now.isoformat(),
        'fecha': now.strftime('%d/%m/%Y'),
        'hora': now.strftime('%H:%M:%S')
    }

    if save_asistencia(asistencia):
        return jsonify({'status': 'ok', 'hora': now.strftime('%H:%M:%S')})
    else:
        return jsonify({'error': 'Error al guardar asistencia'}), 500


@app.route('/api/usuarios')
@cross_origin()
def api_usuarios():
    empleados = get_all_empleados()
    # Agregar información de entrenamiento a cada empleado
    for empleado in empleados:
        entrenamiento = get_entrenamiento_by_empleado(empleado['pem_id'])
        if entrenamiento:
            empleado['entrenamiento'] = {
                'estado': entrenamiento['fac_state'],
                'fecha': entrenamiento['fac_training_date'],
                'num_fotos': entrenamiento['fac_num_photos_captured'],
                'precision': entrenamiento['fac_precision']
            }
        else:
            empleado['entrenamiento'] = None

    return jsonify(empleados)


@app.route('/api/asistencias')
@cross_origin()
def api_asistencias():
    asistencias = get_asistencias(50)  # Últimas 50 asistencias
    return jsonify(asistencias)


@app.route('/api/entrenamiento/eliminar', methods=['DELETE'])
@cross_origin()
def api_eliminar_entrenamiento():
    """Endpoint para eliminar un entrenamiento (registro BD, archivo .yml y cache)"""
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400
    
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    
    entrenamiento = get_entrenamiento_by_empleado(empleado_id)
    if not entrenamiento:
        return jsonify({'error': 'No se encontró entrenamiento para este empleado'}), 404
    
    entrenamiento_id = entrenamiento['fac_id']
    modelo_path = entrenamiento.get('fac_ruta_modelo')
    
    if not delete_entrenamiento(entrenamiento_id, empleado_id):
        return jsonify({'error': 'Error al eliminar registro de base de datos'}), 500
    
    if modelo_path and os.path.exists(modelo_path):
        try:
            os.remove(modelo_path)
        except Exception as e:
            print(f"Error eliminando archivo modelo: {e}")
    
    cache_data = cargar_rostros_cache()
    if empleado_id in cache_data:
        del cache_data[empleado_id]
        guardar_rostros_cache_to_disk(cache_data)
        print(f"[DEBUG] Usuario {empleado_id} eliminado del cache", file=sys.stderr)
    else:
        print(f"[DEBUG] Usuario {empleado_id} NO estaba en cache", file=sys.stderr)
    
    print(f"[DEBUG] Cache después de eliminar: {list(cargar_rostros_cache().keys())}", file=sys.stderr)
    
    global_result = reentrenar_modelo_global()
    if global_result:
        print(f"[DEBUG] Modelo global reentrenado: {global_result}", file=sys.stderr)
    else:
        print(f"[DEBUG] No se pudo reentrenar modelo global (cache vacío?)", file=sys.stderr)
    
    return jsonify({
        'status': 'ok',
        'message': 'Entrenamiento eliminado correctamente',
        'entrenamiento_id': entrenamiento_id,
        'empleado_id': empleado_id
    })


@app.route('/api/entrenamiento/reset-completo', methods=['POST'])
@cross_origin()
def api_reset_completo():
    """Elimina TODO: cache, modelos, y registros de entrenamiento"""
    deleted_files = {'modelos': [], 'cache': []}
    
    if os.path.exists(MODELS_DIR):
        for f in os.listdir(MODELS_DIR):
            fp = os.path.join(MODELS_DIR, f)
            try:
                os.remove(fp)
                deleted_files['modelos'].append(f)
            except: pass
    
    cache_data = {}
    guardar_rostros_cache_to_disk(cache_data)
    deleted_files['cache'].append('rostros_cache.json')
    
    try:
        connection = get_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE tbl_facial_training SET fac_state = 'pendiente' WHERE fac_state IN ('entrenado', 'eliminado')")
            connection.commit()
            deleted_files['db_updated'] = cursor.rowcount
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error en reset DB: {e}")
    
    print(f"[DEBUG] Reset completo ejecutado: {deleted_files}", file=sys.stderr)
    
    return jsonify({
        'status': 'ok',
        'message': 'Sistema reseteado completamente',
        'deleted': deleted_files
    })


@app.route('/api/entrenamiento/estado', methods=['GET'])
@cross_origin()
def api_entrenamiento_estado():
    """Muestra el estado actual del sistema de entrenamiento"""
    cache_data = cargar_rostros_cache()
    
    files = []
    if os.path.exists(MODELS_DIR):
        files = os.listdir(MODELS_DIR)
    
    global_model_exists = os.path.exists(os.path.join(MODELS_DIR, 'modelo_global.yml'))
    labels_exists = os.path.exists(os.path.join(MODELS_DIR, 'labels.json'))
    
    return jsonify({
        'cache_empleados': list(cache_data.keys()),
        'cache_count': len(cache_data),
        'modelos_dir_files': files,
        'modelo_global_existe': global_model_exists,
        'labels_existe': labels_exists,
        'MODELS_DIR': MODELS_DIR
    })


if __name__ == '__main__':
    # Crear directorios necesarios
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Inicializar base de datos
    if not init_db():
        print("ERROR: No se pudo inicializar la base de datos")
        exit(1)

    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   Sistema de Asistencia Facial       ║")
    print("  ║   Backend API + MySQL                ║")
    print("  ║   Abrir: http://localhost:5050       ║")
    print("  ╚══════════════════════════════════════╝\n")

    app.run(
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug']
    )
