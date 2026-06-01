from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import cv2
import numpy as np
import os
import json
import base64
import sys
from datetime import datetime
import shutil

from config import (
    MYSQL_CONFIG, BASE_DIR, DATA_DIR, MODELS_DIR, TOTAL_FOTOS,
    FLASK_CONFIG, SERVER_CONFIG, SIMILARITY_THRESHOLD,
    INSIGHTFACE_MODEL_NAME
)
from database import (
    get_connection, init_db, get_empleado_by_id, get_all_empleados,
    insert_entrenamiento, update_entrenamiento, get_entrenamientos_activos,
    get_entrenamiento_by_empleado, get_asistencias, save_asistencia,
    delete_entrenamiento, get_entrenamiento_by_id, get_empleados_pendientes_entrenamiento,
    init_embeddings_table, count_embedding_blobs, get_pem_id_by_usr_id
)
from services.face_detector import FaceDetector
from services.matcher import FaceMatcher
from services.storage import EmbeddingStorage
from services.liveness import check_liveness as advanced_liveness_check
from services.anti_spoofing import AntiSpoofing

app = Flask(__name__)
app.config.update(FLASK_CONFIG)

CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://localhost:3039",
            "https://pavastecnologia.com",
            "https://www.pavastecnologia.com"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

if not init_db():
    print("ERROR: No se pudo conectar a la base de datos MySQL")
    exit(1)

init_embeddings_table()

# Haar cascade for fast face detection during photo capture only
face_cascade = cv2.CascadeClassifier(
    os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))

# InsightFace-based services
face_detector = None
embedding_storage = None
face_matcher = None
anti_spoofing = None
try:
    face_detector = FaceDetector.get_instance(INSIGHTFACE_MODEL_NAME)
    embedding_storage = EmbeddingStorage()
    face_matcher = FaceMatcher()
    anti_spoofing = AntiSpoofing.get_instance()
    print(f"InsightFace ({INSIGHTFACE_MODEL_NAME}) iniciado correctamente")
    if anti_spoofing.available:
        print("Anti-spoofing (DeePixBiS) disponible")
    else:
        print("Anti-spoofing NO disponible - modelo no encontrado")
except Exception as e:
    print(f"ERROR al iniciar servicios: {e}")
    face_detector = None


def decode_image(b64):
    if not b64:
        raise ValueError("No image data provided")
    if ',' in b64:
        b64 = b64.split(',')[1]
    try:
        data = base64.b64decode(b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 data: {e}")
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'La imagen es demasiado grande. Maximo 10MB permitido.'}), 413


@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Solicitud invalida'}), 400


def check_liveness(face_gray, face_bgr=None, det_score=None):
    return advanced_liveness_check(face_gray, face_bgr=face_bgr, det_score=det_score)


# ---------------------------------------------------------------------------
# Photo capture endpoints (unchanged behavior)
# ---------------------------------------------------------------------------

@app.route('/api/registrar/frame', methods=['POST'])

def api_registrar_frame():
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    try:
        frame = decode_image(data['image'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
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
    folder = os.path.join(DATA_DIR, empleado_id)
    os.makedirs(folder, exist_ok=True)
    count = len([f for f in os.listdir(folder) if f.endswith('.jpg')])
    if count >= TOTAL_FOTOS:
        return jsonify({'status': 'complete', 'count': count})
    margin = int(max(w, h) * 0.3)
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(frame.shape[1], x + w + margin)
    y2 = min(frame.shape[0], y + h + margin)
    face_crop = frame[y1:y2, x1:x2]
    face_resized = cv2.resize(face_crop, (160, 160),
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

def api_registrar_fin():
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    folder = os.path.join(DATA_DIR, empleado_id)
    if not os.path.exists(folder):
        return jsonify({'error': 'Sin datos de fotos'}), 400
    count = len([f for f in os.listdir(folder) if f.endswith('.jpg')])
    if count == 0:
        return jsonify({'error': 'No hay fotos capturadas'}), 400
    entrenamiento_id = insert_entrenamiento(empleado_id, count, empleado['usr_id'])
    if not entrenamiento_id:
        return jsonify({'error': 'Error al guardar en base de datos'}), 500
    return jsonify({
        'status': 'ok',
        'count': count,
        'entrenamiento_id': entrenamiento_id,
        'empleado_id': empleado_id
    })


# ---------------------------------------------------------------------------
# Training / embedding extraction (replaces LBPH training)
# ---------------------------------------------------------------------------

@app.route('/api/entrenar', methods=['POST'])

def api_entrenar():
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

    face_count = len([f for f in os.listdir(folder) if f.endswith('.jpg')])
    if face_count == 0:
        return jsonify({'error': 'No hay fotos para entrenar'}), 400

    # Reset training state to pending (allows retraining at any time)
    usr_id = empleado['usr_id']
    entrenamiento_id = insert_entrenamiento(empleado_id, face_count, usr_id)
    if not entrenamiento_id:
        return jsonify({'error': 'Error al crear registro de entrenamiento'}), 500
    entrenamiento = get_entrenamiento_by_id(entrenamiento_id)

    if face_detector is None:
        return jsonify({'error': 'InsightFace no esta disponible'}), 500

    embeddings = []
    det_scores = []

    for img_file in sorted(os.listdir(folder)):
        if not img_file.endswith('.jpg'):
            continue
        img_path = os.path.join(folder, img_file)
        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            continue
        emb, score = face_detector.extract_embedding(img)
        if emb is not None:
            embeddings.append(emb)
            det_scores.append(score)

    if not embeddings:
        return jsonify({'error': 'No se pudieron extraer rostros de las imagenes'}), 400

    embedding_storage.save_user_embeddings(usr_id, embeddings)
    precision = round(float(np.mean(det_scores)), 4)

    updates = {
        'fac_state': 'trained',
        'fac_ruta_modelo': '',
        'fac_precision': precision
    }
    if not update_entrenamiento(entrenamiento['fac_id'], updates, usr_id):
        return jsonify({'error': 'Error al actualizar base de datos'}), 500

    try:
        shutil.rmtree(folder)
    except Exception as e:
        print(f"Error eliminando carpeta: {e}")

    response = {
        'status': 'ok',
        'empleado_id': empleado_id,
        'entrenamiento_id': entrenamiento['fac_id'],
        'imagenes_entrenadas': len(embeddings),
        'precision': precision,
        'modelo_path': ''
    }

    all_embs = embedding_storage.get_all()
    response['modelo_global'] = {
        'empleados_entrenados': len(all_embs),
        'total_imagenes': sum(len(v) for v in all_embs.values()),
        'modelo_path': 'embedding_db'
    }

    return jsonify(response)


@app.route('/api/entrenar-individual', methods=['POST'])

def api_entrenar_individual():
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

    if face_detector is None:
        return jsonify({'error': 'InsightFace no esta disponible'}), 500

    usr_id = empleado['usr_id']
    face_count = len([f for f in os.listdir(folder) if f.endswith('.jpg')])
    if face_count == 0:
        return jsonify({'error': 'No hay fotos para entrenar'}), 400

    # Reset training state to pending (allows retraining at any time)
    entrenamiento_id = insert_entrenamiento(empleado_id, face_count, usr_id)
    entrenamiento = get_entrenamiento_by_id(entrenamiento_id) if entrenamiento_id else None

    embeddings = []
    det_scores = []

    for img_file in sorted(os.listdir(folder)):
        if not img_file.endswith('.jpg'):
            continue
        img_path = os.path.join(folder, img_file)
        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            continue
        emb, score = face_detector.extract_embedding(img)
        if emb is not None:
            embeddings.append(emb)
            det_scores.append(score)

    if not embeddings:
        return jsonify({'error': 'No se pudieron extraer rostros de las imagenes'}), 400

    embedding_storage.save_user_embeddings(usr_id, embeddings)
    precision = round(float(np.mean(det_scores)), 4)

    if entrenamiento:
        update_entrenamiento(entrenamiento['fac_id'], {
            'fac_state': 'trained',
            'fac_ruta_modelo': '',
            'fac_precision': precision
        }, usr_id)

    try:
        shutil.rmtree(folder)
    except Exception as e:
        print(f"Error eliminando carpeta: {e}")

    response = {
        'status': 'ok',
        'empleado_id': empleado_id,
        'rostros_guardados_cache': len(embeddings),
        'modelo_path': ''
    }

    all_embs = embedding_storage.get_all()
    response['modelo_global'] = {
        'empleados_entrenados': len(all_embs),
        'total_imagenes': sum(len(v) for v in all_embs.values()),
        'modelo_path': 'embedding_db'
    }

    return jsonify(response)


@app.route('/api/entrenar-global', methods=['POST'])

def api_entrenar_global():
    """No global model necessary — embeddings are stored per-user."""
    all_embs = embedding_storage.get_all() if embedding_storage else {}
    total = sum(len(v) for v in all_embs.values()) if all_embs else 0

    if total == 0:
        return jsonify({'error': 'No hay embeddings almacenados'}), 400

    return jsonify({
        'status': 'ok',
        'empleados_entrenados': len(all_embs),
        'total_imagenes': total,
        'modelo_path': 'embedding_db'
    })


# ---------------------------------------------------------------------------
# Recognition (embedding matching, replaces LBPH prediction)
# ---------------------------------------------------------------------------

@app.route('/api/reconocer', methods=['POST'])

def api_reconocer():
    if face_detector is None or embedding_storage is None:
        return jsonify({'error': 'InsightFace no esta disponible'}), 500

    try:
        frame = decode_image(request.json['image'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    detections = face_detector.detect_and_extract(frame)

    if not detections:
        return jsonify({'faces': []})

    user_embeddings = embedding_storage.get_all()

    if not user_embeddings:
        return jsonify({'error': 'No hay usuarios registrados en el sistema'}), 400

    results = []
    for det in detections:
        bbox = det['bbox']
        x, y = bbox[0], bbox[1]
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        if anti_spoofing and anti_spoofing.available:
            is_real_as, conf_as = anti_spoofing.predict(frame, (x, y, w, h))
            if not is_real_as:
                results.append({
                    'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                    'empleado_id': None,
                    'nombre': 'FOTO DETECTADA',
                    'confianza': 0,
                    'valido': False
                })
                continue

        best_id, best_sim = face_matcher.find_best_match(
            det['embedding'], user_embeddings, SIMILARITY_THRESHOLD
        )

        confianza_pct = max(0, round(best_sim * 100))

        if best_id:
            emp = get_empleado_by_id(best_id)
            nombre = emp['pem_full_name'] if emp else 'Desconocido'
            # Return pem_id for frontend compatibility (old LBPH system used
            # whatever id the frontend sent during enrollment, which was pem_id)
            pem_id = get_pem_id_by_usr_id(best_id)
            results.append({
                'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h),
                'empleado_id': pem_id or best_id,
                'nombre': nombre,
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


# ---------------------------------------------------------------------------
# Attendance (unchanged)
# ---------------------------------------------------------------------------

@app.route('/api/asistencia', methods=['POST'])

def api_asistencia():
    empleado_id = request.json.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    entrenamiento = get_entrenamiento_by_empleado(empleado_id)
    if not entrenamiento or entrenamiento['fac_state'] != 'trained':
        return jsonify({'error': 'Empleado no tiene entrenamiento activo'}), 400
    now = datetime.now()
    usr_id = empleado['usr_id']
    asistencias = get_asistencias(50)
    for a in reversed(asistencias):
        if a.get('empleado_id') == usr_id:
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
    asistencia = {
        'empleado_id': usr_id,
        'usuario': empleado['pem_full_name'],
        'timestamp': now.isoformat(),
        'fecha': now.strftime('%d/%m/%Y'),
        'hora': now.strftime('%H:%M:%S')
    }
    if save_asistencia(asistencia):
        return jsonify({'status': 'ok', 'hora': now.strftime('%H:%M:%S')})
    else:
        return jsonify({'error': 'Error al guardar asistencia'}), 500


# ---------------------------------------------------------------------------
# User listing (unchanged shape)
# ---------------------------------------------------------------------------

@app.route('/api/usuarios')

def api_usuarios():
    empleados = get_all_empleados()
    for empleado in empleados:
        entrenamiento = get_entrenamiento_by_empleado(empleado['usr_id'])
        if entrenamiento:
            empleado['entrenamiento'] = {
                'estado': entrenamiento['fac_state'],
                'fecha': entrenamiento['fac_training_date'],
                'num_fotos': entrenamiento['fac_num_photos_captured'],
                'precision': entrenamiento.get('fac_precision', 0)
            }
        else:
            empleado['entrenamiento'] = None
    return jsonify(empleados)


@app.route('/api/asistencias')

def api_asistencias():
    asistencias = get_asistencias(50)
    return jsonify(asistencias)


# ---------------------------------------------------------------------------
# Training management
# ---------------------------------------------------------------------------

@app.route('/api/entrenamiento/eliminar', methods=['DELETE'])

def api_eliminar_entrenamiento():
    data = request.json
    empleado_id = data.get('empleado_id', '').strip()
    if not empleado_id:
        return jsonify({'error': 'Empleado ID requerido'}), 400
    empleado = get_empleado_by_id(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    entrenamiento = get_entrenamiento_by_empleado(empleado_id)
    if not entrenamiento:
        return jsonify({'error': 'No se encontro entrenamiento para este empleado'}), 404

    entrenamiento_id = entrenamiento['fac_id']
    modelo_path = entrenamiento.get('fac_ruta_modelo')

    if not delete_entrenamiento(entrenamiento_id, empleado_id):
        return jsonify({'error': 'Error al eliminar registro de base de datos'}), 500

    if modelo_path and os.path.exists(modelo_path):
        try:
            os.remove(modelo_path)
        except Exception as e:
            print(f"Error eliminando archivo modelo: {e}")

    if embedding_storage:
        embedding_storage.delete_user_embeddings(empleado['usr_id'])

    clean_cache_entry(empleado_id)

    return jsonify({
        'status': 'ok',
        'message': 'Entrenamiento eliminado correctamente',
        'entrenamiento_id': entrenamiento_id,
        'empleado_id': empleado_id
    })


@app.route('/api/entrenamiento/reset-completo', methods=['POST'])

def api_reset_completo():
    deleted_files = {'modelos': [], 'cache': []}

    if os.path.exists(MODELS_DIR):
        for f in os.listdir(MODELS_DIR):
            fp = os.path.join(MODELS_DIR, f)
            try:
                os.remove(fp)
                deleted_files['modelos'].append(f)
            except:
                pass

    cache_path = os.path.join(MODELS_DIR, 'rostros_cache.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'w') as f:
                json.dump({}, f)
            deleted_files['cache'].append('rostros_cache.json')
        except:
            pass

    if embedding_storage:
        count = embedding_storage.delete_all()
        deleted_files['embeddings_eliminados'] = count

    try:
        connection = get_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE tbl_facial_training SET fac_state = 'pending' WHERE fac_state IN ('trained', 'failed')")
            connection.commit()
            deleted_files['db_updated'] = cursor.rowcount
            cursor.close()
            connection.close()
    except Exception as e:
        print(f"Error en reset DB: {e}")

    return jsonify({
        'status': 'ok',
        'message': 'Sistema reseteado completamente',
        'deleted': deleted_files
    })


@app.route('/api/entrenamiento/estado', methods=['GET'])

def api_entrenamiento_estado():
    files = []
    if os.path.exists(MODELS_DIR):
        files = os.listdir(MODELS_DIR)
    global_model_exists = os.path.exists(os.path.join(MODELS_DIR, 'modelo_global.yml'))
    labels_exists = os.path.exists(os.path.join(MODELS_DIR, 'labels.json'))
    emb_count = embedding_storage.count() if embedding_storage else 0
    emb_users = len(embedding_storage.get_all()) if embedding_storage else 0

    return jsonify({
        'cache_empleados': list(embedding_storage.get_all().keys()) if embedding_storage else [],
        'cache_count': emb_users,
        'modelos_dir_files': files,
        'modelo_global_existe': global_model_exists,
        'labels_existe': labels_exists,
        'MODELS_DIR': MODELS_DIR,
        'total_embeddings': emb_count,
        'total_usuarios_embeddings': emb_users
    })


# ---------------------------------------------------------------------------
# Utility helpers (kept for backward compat with legacy file references)
# ---------------------------------------------------------------------------

def clean_cache_entry(empleado_id):
    cache_path = os.path.join(MODELS_DIR, 'rostros_cache.json')
    if not os.path.exists(cache_path):
        return
    try:
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)
        if empleado_id in cache_data:
            del cache_data[empleado_id]
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"Error limpiando cache: {e}")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)
    if not init_db():
        print("ERROR: No se pudo inicializar la base de datos")
        exit(1)
    print("\n  ========================================")
    print("     Sistema de Asistencia Facial")
    print("     Backend API + MySQL + InsightFace")
    print(f"     Abrir: http://localhost:{SERVER_CONFIG['port']}")
    print("  ========================================\n")
    app.run(
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug']
    )
