import mysql.connector
from mysql.connector import Error
from config import MYSQL_CONFIG
import uuid
from datetime import datetime

def get_connection():
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        return connection
    except Error as e:
        print(f"Error conectando a MySQL: {e}")
        return None

def init_db():
    connection = get_connection()
    if connection is None:
        return False
    try:
        print("Conexion con MySQL OK")
        return True
    except Error as e:
        print(f"Error inicializando BD: {e}")
        return False
    finally:
        if connection.is_connected():
            connection.close()


def get_pem_id_by_usr_id(usr_id):
    connection = get_connection()
    if not connection:
        return None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT pem_id FROM tbl_pay_employees WHERE usr_id = %s AND pem_deleted = 0 LIMIT 1", (usr_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Error as e:
        print(f"Error obteniendo pem_id: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_empleado_by_id(empleado_id):
    """Find user by usr_id (self-clock) or pem_id (employee management)"""
    connection = get_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        # Try as usr_id first
        query = "SELECT usr_id, usr_name AS pem_full_name, usr_email AS pem_email FROM tbl_users WHERE usr_id = %s"
        cursor.execute(query, (empleado_id,))
        result = cursor.fetchone()
        if result:
            return result
        # Try as pem_id -> find linked usr_id
        query = """SELECT u.usr_id, u.usr_name AS pem_full_name, u.usr_email AS pem_email
                   FROM tbl_users u
                   INNER JOIN tbl_pay_employees pe ON pe.usr_id = u.usr_id
                   WHERE pe.pem_id = %s"""
        cursor.execute(query, (empleado_id,))
        return cursor.fetchone()
    except Error as e:
        print(f"Error obteniendo usuario: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_all_empleados():
    connection = get_connection()
    if connection is None:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        query = """SELECT DISTINCT u.usr_id, u.usr_name AS pem_full_name, u.usr_email AS pem_email
                   FROM tbl_users u
                   INNER JOIN tbl_pay_employees pe ON pe.usr_id = u.usr_id
                   WHERE pe.pem_deleted = 0
                   ORDER BY u.usr_name"""
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Error obteniendo usuarios: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def _resolve_usr_id(empleado_id):
    """Helper: resolve pem_id to usr_id if needed"""
    empleado = get_empleado_by_id(empleado_id)
    if empleado:
        return empleado['usr_id']
    return empleado_id

def save_or_update_entrenamiento(empleado_id, num_fotos, created_by=None):
    connection = get_connection()
    if connection is None:
        return None
    try:
        if created_by:
            created_by = created_by
        cursor = connection.cursor(dictionary=True)
        query_check = "SELECT fac_id FROM tbl_facial_training WHERE fk_pem_id = %s"
        cursor.execute(query_check, (empleado_id,))
        existing_records = cursor.fetchall()

        if existing_records and len(existing_records) > 0:
            entrenamiento_id = existing_records[0]['fac_id']
            if len(existing_records) > 1:
                for record in existing_records[1:]:
                    delete_query = "DELETE FROM tbl_facial_training WHERE fac_id = %s"
                    cursor.execute(delete_query, (record['fac_id'],))
            query_update = """
            UPDATE tbl_facial_training
            SET fac_num_photos_captured = %s,
                fac_training_date = %s,
                fac_state = %s,
                fac_updated_by = %s,
                fac_ruta_modelo = NULL,
                fac_precision = NULL
            WHERE fac_id = %s
            """
            cursor.execute(query_update, (
                num_fotos,
                datetime.now(),
                'pending',
                created_by or empleado_id,
                entrenamiento_id
            ))
            connection.commit()
            return entrenamiento_id
        else:
            entrenamiento_id = str(uuid.uuid4())
            query_insert = """
            INSERT INTO tbl_facial_training
            (fac_id, fk_pem_id, fac_training_date, fac_num_photos_captured, fac_state, fac_created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_insert, (
                entrenamiento_id,
                empleado_id,
                datetime.now(),
                num_fotos,
                'pending',
                created_by or empleado_id
            ))
            connection.commit()
            return entrenamiento_id
    except Error as e:
        print(f"Error en save_or_update_entrenamiento: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def insert_entrenamiento(empleado_id, num_fotos, created_by=None):
    return save_or_update_entrenamiento(empleado_id, num_fotos, created_by)

def update_entrenamiento(entrenamiento_id, updates, updated_by=None):
    connection = get_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        set_parts = []
        values = []
        for key, value in updates.items():
            if key in ['fac_state', 'fac_ruta_modelo', 'fac_precision']:
                set_parts.append(f"{key} = %s")
                values.append(value)
        if not set_parts:
            return False
        set_parts.append("fac_updated_by = %s")
        values.append(updated_by or 'system')
        query = f"UPDATE tbl_facial_training SET {', '.join(set_parts)} WHERE fac_id = %s"
        values.append(entrenamiento_id)
        cursor.execute(query, values)
        connection.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error actualizando entrenamiento: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_entrenamientos_activos():
    connection = get_connection()
    if connection is None:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT ft.fac_id, ft.fk_pem_id, ft.fac_ruta_modelo
        FROM tbl_facial_training ft
        WHERE ft.fac_state = 'trained'
        ORDER BY ft.fac_updated_at DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Error obteniendo entrenamientos activos: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_empleados_pendientes_entrenamiento():
    connection = get_connection()
    if connection is None:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT ft.fk_pem_id
        FROM tbl_facial_training ft
        WHERE ft.fac_state = 'pending'
        ORDER BY ft.fac_updated_at ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return [r['fk_pem_id'] for r in results]
    except Error as e:
        print(f"Error obteniendo pendientes: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_entrenamiento_by_empleado(empleado_id):
    connection = get_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT * FROM tbl_facial_training
        WHERE fk_pem_id = %s
        ORDER BY fac_updated_at DESC
        LIMIT 1
        """
        cursor.execute(query, (empleado_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Error obteniendo entrenamiento: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_entrenamiento_by_id(entrenamiento_id):
    connection = get_connection()
    if connection is None:
        return None
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM tbl_facial_training WHERE fac_id = %s"
        cursor.execute(query, (entrenamiento_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Error obteniendo entrenamiento por ID: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def delete_entrenamiento(entrenamiento_id, empleado_id=None):
    connection = get_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        if empleado_id:
            query = "DELETE FROM tbl_facial_training WHERE fac_id = %s AND fk_pem_id = %s"
            cursor.execute(query, (entrenamiento_id, empleado_id))
        else:
            query = "DELETE FROM tbl_facial_training WHERE fac_id = %s"
            cursor.execute(query, (entrenamiento_id,))
        connection.commit()
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error eliminando entrenamiento: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_asistencias(limit=50):
    try:
        connection = get_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT a.att_id AS id,
                        a.usr_id AS empleado_id,
                        u.usr_name AS nombre,
                        a.att_timestamp AS timestamp,
                        a.att_status AS status,
                        a.att_source AS source,
                        a.att_device_uid AS device_name
                FROM tbl_attendances a
                JOIN tbl_users u ON a.usr_id = u.usr_id
                ORDER BY a.att_timestamp DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
            asistencias = cursor.fetchall()
            cursor.close()
            connection.close()
            return asistencias
        return []
    except Exception as e:
        print(f"Error obteniendo asistencias: {e}")
        return []

def save_asistencia(asistencia):
    try:
        connection = get_connection()
        if connection:
            cursor = connection.cursor()
            query = """
                INSERT INTO tbl_attendances
                (usr_id, att_timestamp, att_status, att_source, att_notes, att_created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                asistencia['empleado_id'],
                asistencia['timestamp'],
                asistencia.get('status', 'present'),
                asistencia.get('source', 'api'),
                asistencia.get('notes', ''),
                asistencia.get('created_by', asistencia['empleado_id'])
            ))
            connection.commit()
            cursor.close()
            connection.close()
            return True
        return False
    except Exception as e:
        print(f"Error guardando asistencia: {e}")
        return False


# ---------------------------------------------------------------------------
# Facial embeddings table (replaces per-user models + cache)
# ---------------------------------------------------------------------------

def init_embeddings_table():
    connection = get_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()
        query = """
        CREATE TABLE IF NOT EXISTS tbl_facial_embeddings (
            emb_id VARCHAR(36) PRIMARY KEY,
            usr_id VARCHAR(36) NOT NULL,
            embedding BLOB NOT NULL,
            thumbnail LONGBLOB,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usr_id) REFERENCES tbl_users(usr_id) ON DELETE CASCADE
        )
        """
        cursor.execute(query)
        connection.commit()
        return True
    except Error as e:
        print(f"Error creando tabla de embeddings: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def save_embedding_blob(usr_id, embedding_blob, thumbnail_blob=None):
    connection = get_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()
        emb_id = str(uuid.uuid4())
        query = """
        INSERT INTO tbl_facial_embeddings (emb_id, usr_id, embedding, thumbnail, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (emb_id, usr_id, embedding_blob, thumbnail_blob, datetime.now()))
        connection.commit()
        return True
    except Error as e:
        print(f"Error guardando embedding: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def load_all_embedding_blobs():
    connection = get_connection()
    if not connection:
        return []
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT usr_id, embedding FROM tbl_facial_embeddings ORDER BY created_at")
        return cursor.fetchall()
    except Error as e:
        print(f"Error cargando embeddings: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def delete_embedding_blobs_by_user(usr_id):
    connection = get_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM tbl_facial_embeddings WHERE usr_id = %s", (usr_id,))
        connection.commit()
        return True
    except Error as e:
        print(f"Error eliminando embeddings de usuario: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def delete_all_embedding_blobs():
    connection = get_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM tbl_facial_embeddings")
        connection.commit()
        return cursor.rowcount
    except Error as e:
        print(f"Error eliminando todos los embeddings: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def count_embedding_blobs(usr_id=None):
    connection = get_connection()
    if not connection:
        return 0
    try:
        cursor = connection.cursor()
        if usr_id:
            cursor.execute("SELECT COUNT(*) FROM tbl_facial_embeddings WHERE usr_id = %s", (usr_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM tbl_facial_embeddings")
        return cursor.fetchone()[0]
    except Error as e:
        print(f"Error contando embeddings: {e}")
        return 0
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
