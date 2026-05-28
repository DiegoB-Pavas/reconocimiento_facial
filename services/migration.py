"""One-time migration: convert legacy LBPH cache data to InsightFace embeddings.

Usage: python -m services.migration
"""
import os
import sys
import json
import base64 as b64
import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import MODELS_DIR
from database import (
    init_db, init_embeddings_table, get_entrenamiento_by_empleado,
    update_entrenamiento, save_embedding_blob,
    delete_embedding_blobs_by_user, count_embedding_blobs
)
from services.face_detector import FaceDetector


def migrate_from_cache():
    legacy_cache_path = os.path.join(os.path.dirname(MODELS_DIR), 'modelos_legacy', 'rostros_cache.json')

    if not os.path.exists(legacy_cache_path):
        print("No se encuentra archivo de cache legacy en", legacy_cache_path)
        return

    if not init_db():
        print("ERROR: No se pudo conectar a la base de datos")
        return

    init_embeddings_table()

    try:
        face_detector = FaceDetector.get_instance('buffalo_l')
    except Exception as e:
        print(f"ERROR al iniciar InsightFace: {e}")
        return

    with open(legacy_cache_path, 'r') as f:
        cache_data = json.load(f)

    if not cache_data:
        print("Cache vacio — no hay datos para migrar")
        return

    total_converted = 0
    total_failed = 0
    total_users = 0

    for empleado_id, data in cache_data.items():
        rostros_b64 = data.get('rostros_base64', [])
        if not rostros_b64:
            continue

        existing = count_embedding_blobs(empleado_id)
        if existing > 0:
            print(f"  [{empleado_id}] ya tiene {existing} embeddings — saltando")
            continue

        embeddings = []
        scores = []

        for i, face_b64 in enumerate(rostros_b64):
            try:
                img_data = b64.b64decode(face_b64)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    continue

                emb, score = face_detector.extract_embedding(img)
                if emb is not None:
                    embeddings.append(emb)
                    scores.append(score)
            except Exception as e:
                print(f"  Error procesando imagen {i} de {empleado_id}: {e}")

        if not embeddings:
            print(f"  [{empleado_id}] no se pudieron extraer embeddings")
            total_failed += 1
            continue

        for emb in embeddings:
            save_embedding_blob(empleado_id, emb.tobytes())

        entrenamiento = get_entrenamiento_by_empleado(empleado_id)
        if entrenamiento and entrenamiento['fac_state'] == 'trained':
            precision = round(float(np.mean(scores)), 4)
            update_entrenamiento(entrenamiento['fac_id'], {
                'fac_state': 'trained',
                'fac_ruta_modelo': '',
                'fac_precision': precision
            }, empleado_id)

        total_converted += len(embeddings)
        total_users += 1
        print(f"  [{empleado_id}] {len(embeddings)} rostros convertidos, precision={np.mean(scores):.4f}")

    print(f"\nMigracion completada: {total_users} usuarios, {total_converted} embeddings, {total_failed} fallos")


if __name__ == '__main__':
    migrate_from_cache()
