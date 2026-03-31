# database.py - Funciones de conexión y operaciones MySQL
import mysql.connector
from mysql.connector import Error
from config import MYSQL_CONFIG
import uuid
from datetime import datetime
import os  # Agregado para compatibilidad con JSON

def get_connection():
    """Establece conexión con MySQL"""
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        return connection
    except Error as e:
        print(f"Error conectando a MySQL: {e}")
        return None

def init_db():
    """Inicializa la base de datos (las tablas se manejan manualmente)"""
    connection = get_connection()
    if connection is None:
        return False

    try:
        # La creación de tablas es manual y se ejecuta por el DBA/cliente.
        # tbl_facial_training y tbl_attendances deben existir en la base de datos.
        print("Conexión con MySQL OK; la creación de tablas se hace manualmente")
        return True

    except Error as e:
        print(f"Error inicializando BD: {e}")
        return False

    finally:
        if connection.is_connected():
            connection.close()

# Funciones CRUD para empleados
def get_empleado_by_id(empleado_id):
    """Obtiene empleado por ID"""
    connection = get_connection()
    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT pem_id, pem_full_name, pem_email FROM tbl_pay_employees WHERE pem_id = %s"
        cursor.execute(query, (empleado_id,))
        result = cursor.fetchone()
        return result
    except Error as e:
        print(f"Error obteniendo empleado: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_all_empleados():
    """Obtiene todos los empleados"""
    connection = get_connection()
    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT pem_id, pem_full_name, pem_email FROM tbl_pay_employees ORDER BY pem_full_name"
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Error obteniendo empleados: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Funciones CRUD para entrenamientos faciales
def save_or_update_entrenamiento(empleado_id, num_fotos, created_by=None):
    """Inserta o actualiza un registro de entrenamiento para un empleado"""
    connection = get_connection()
    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        
        # Verificar si ya existe un registro para este empleado
        query_check = "SELECT fac_id FROM tbl_facial_training WHERE fk_pem_id = %s"
        cursor.execute(query_check, (empleado_id,))
        existing = cursor.fetchone()

        if existing:
            # Actualizar registro existente
            entrenamiento_id = existing['fac_id']
            query_update = """
            UPDATE tbl_facial_training 
            SET fac_num_photos_captured = %s, 
                fac_training_date = %s,
                fac_state = %s,
                fac_updated_by = %s
            WHERE fac_id = %s
            """
            cursor.execute(query_update, (
                num_fotos,
                datetime.now(),
                'pendiente',
                created_by or empleado_id,
                entrenamiento_id
            ))
            connection.commit()
            return entrenamiento_id
        else:
            # Insertar uno nuevo si no existe
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
                'pendiente',
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
    """Mantiene compatibilidad: llama a save_or_update_entrenamiento"""
    return save_or_update_entrenamiento(empleado_id, num_fotos, created_by)

def update_entrenamiento(entrenamiento_id, updates, updated_by=None):
    """Actualiza registro de entrenamiento"""
    connection = get_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        # Construir query dinámicamente
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
    """Obtiene todos los entrenamientos con estado 'entrenado'"""
    connection = get_connection()
    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT ft.fac_id, ft.fk_pem_id, ft.fac_ruta_modelo, e.pem_full_name
        FROM tbl_facial_training ft
        JOIN tbl_pay_employees e ON ft.fk_pem_id = e.pem_id
        WHERE ft.fac_state = 'entrenado'
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

def get_entrenamiento_by_empleado(empleado_id):
    """Obtiene el último entrenamiento de un empleado"""
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
        print(f"Error obteniendo entrenamiento por empleado: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_entrenamiento_by_id(entrenamiento_id):
    """Obtiene el entrenamiento por su ID"""
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
    """Elimina un registro de entrenamiento por su ID"""
    connection = get_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        
        if empleado_id:
            # Si se proporciona empleado_id, verificamos que coincida por seguridad
            query = "DELETE FROM tbl_facial_training WHERE fac_id = %s AND fk_pem_id = %s"
            cursor.execute(query, (entrenamiento_id, empleado_id))
        else:
            # Solo eliminamos por fac_id
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

# Funciones para asistencias (MySQL)
def get_asistencias(limit=50):
    """Obtiene últimas asistencias desde tbl_attendances"""
    try:
        connection = get_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT a.att_id AS id,
                        a.pem_id AS empleado_id,
                        e.pem_full_name AS nombre,
                        a.att_timestamp AS timestamp,
                        a.att_status AS status,
                        a.att_source AS source,
                        a.att_device_name AS device_name
                FROM tbl_attendances a
                JOIN tbl_pay_employees e ON a.pem_id = e.pem_id
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
    """Guarda asistencia en tbl_attendances"""
    try:
        connection = get_connection()
        if connection:
            cursor = connection.cursor()
            query = """
                INSERT INTO tbl_attendances
                (pem_id, att_timestamp, att_status, att_source, att_notes, att_created_by)
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