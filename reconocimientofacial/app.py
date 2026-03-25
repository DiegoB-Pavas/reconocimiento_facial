from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import cv2
import numpy as np
import os
import json
import base64
from datetime import datetime
import shutil  # Para eliminar carpetas

# Importar configuración y base de datos
from config import MYSQL_CONFIG, BASE_DIR, DATA_DIR, MODELS_DIR, TOTAL_FOTOS, FLASK_CONFIG, SERVER_CONFIG
from database import (
    get_connection, init_db, get_empleado_by_id, get_all_empleados,
    insert_entrenamiento, update_entrenamiento, get_entrenamientos_activos,
    get_entrenamiento_by_empleado, get_asistencias, save_asistencia
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
        # No fallar el entrenamiento por esto

    return jsonify({
        'status': 'ok',
        'empleado_id': empleado_id,
        'entrenamiento_id': entrenamiento['fac_id'],
        'imagenes_entrenadas': len(faces),
        'precision': precision,
        'modelo_path': modelo_path
    })


@app.route('/api/reconocer', methods=['POST'])
@cross_origin()
def api_reconocer():
    # Obtener todos los entrenamientos activos
    entrenamientos = get_entrenamientos_activos()
    if not entrenamientos:
        return jsonify({'error': 'No hay modelos entrenados'}), 400

    frame = decode_image(request.json['image'])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

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

        # Probar contra todos los modelos entrenados
        best_match = None
        best_confidence = float('inf')
        best_usuario = None

        for entrenamiento in entrenamientos:
            model_path = entrenamiento['fac_ruta_modelo']
            if not os.path.exists(model_path):
                continue

            try:
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                recognizer.read(model_path)

                label_id, confidence = recognizer.predict(face_roi)

                # Para modelos individuales, label_id siempre es 0
                # Usamos el confidence para determinar el mejor match
                if confidence < best_confidence:
                    best_confidence = confidence
                    best_match = entrenamiento
                    best_usuario = {
                        'empleado_id': entrenamiento['fk_pem_id'],
                        'nombre': entrenamiento['pem_full_name']
                    }
            except Exception as e:
                print(f"Error cargando modelo {model_path}: {e}")
                continue

        # LBPH: menor confidence = mejor coincidencia
        valido = best_confidence < 80 if best_confidence != float('inf') else False

        if valido and best_usuario:
            results.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'empleado_id': best_usuario['empleado_id'],
                'nombre': best_usuario['nombre'],
                'confianza': max(0, round(100 - best_confidence)),
                'valido': True
            })
        else:
            results.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'empleado_id': None,
                'nombre': 'Desconocido',
                'confianza': 0,
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
    print("  ║   Abrir: http://localhost:5000       ║")
    print("  ╚══════════════════════════════════════╝\n")

    app.run(
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug']
    )
