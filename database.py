# database.py
import sqlite3
from sqlite3 import Error

DATABASE_NAME = "audiencias.db"

def crear_conexion():
    """Crea una conexión a la base de datos SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        # print(f"Conexión a {DATABASE_NAME} exitosa (SQLite v{sqlite3.sqlite_version})")
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
    return conn

def crear_tabla(conn):
    """Crea la tabla de eventos si no existe."""
    sql_crear_tabla_eventos = """
    CREATE TABLE IF NOT EXISTS eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL, -- Formato YYYY-MM-DD
        hora TEXT,          -- Formato HH:MM (Opcional)
        link TEXT,
        descripcion TEXT,
        recordatorio_activo INTEGER DEFAULT 0, -- 0: No, 1: Sí
        recordatorio_minutos INTEGER DEFAULT 15 -- Minutos antes del evento
    );
    """
    try:
        cursor = conn.cursor()
        cursor.execute(sql_crear_tabla_eventos)
        # print("Tabla 'eventos' verificada/creada.")
    except Error as e:
        print(f"Error al crear la tabla: {e}")

def inicializar_db():
    """Inicializa la base de datos y crea la tabla."""
    conn = crear_conexion()
    if conn is not None:
        crear_tabla(conn)
        conn.close()
    else:
        print("Error: No se pudo crear la conexión a la base de datos.")

# --- Funciones CRUD (Create, Read, Update, Delete) ---

def agregar_evento(fecha, hora, link, descripcion, recordatorio_activo, recordatorio_minutos):
    conn = crear_conexion()
    sql = '''INSERT INTO eventos(fecha, hora, link, descripcion, recordatorio_activo, recordatorio_minutos)
             VALUES(?,?,?,?,?,?)'''
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (fecha, hora, link, descripcion, recordatorio_activo, recordatorio_minutos))
        conn.commit()
        # print("Evento agregado con ID:", cursor.lastrowid)
        return cursor.lastrowid
    except Error as e:
        print(f"Error al agregar evento: {e}")
        return None
    finally:
        if conn:
            conn.close()

def obtener_eventos_por_fecha(fecha):
    conn = crear_conexion()
    eventos = []
    sql = "SELECT * FROM eventos WHERE fecha = ? ORDER BY hora"
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (fecha,))
        rows = cursor.fetchall()
        # Convertir filas a diccionarios para fácil acceso
        columnas = [descripcion[0] for descripcion in cursor.description]
        for row in rows:
            eventos.append(dict(zip(columnas, row)))
        # print(f"Eventos encontrados para {fecha}: {len(eventos)}")
    except Error as e:
        print(f"Error al obtener eventos: {e}")
    finally:
        if conn:
            conn.close()
    return eventos

def obtener_todos_eventos_con_recordatorio():
    conn = crear_conexion()
    eventos = []
    # Selecciona eventos futuros o de hoy con recordatorio activo
    sql = """
        SELECT * FROM eventos
        WHERE recordatorio_activo = 1 AND date(fecha || ' ' || time(COALESCE(hora, '00:00') || ':00')) >= date('now', 'localtime')
        ORDER BY fecha, hora
        """
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columnas = [descripcion[0] for descripcion in cursor.description]
        for row in rows:
            eventos.append(dict(zip(columnas, row)))
    except Error as e:
        print(f"Error al obtener eventos con recordatorio: {e}")
    finally:
        if conn:
            conn.close()
    return eventos


def actualizar_evento(id_evento, fecha, hora, link, descripcion, recordatorio_activo, recordatorio_minutos):
    conn = crear_conexion()
    sql = '''UPDATE eventos
             SET fecha = ?, hora = ?, link = ?, descripcion = ?,
                 recordatorio_activo = ?, recordatorio_minutos = ?
             WHERE id = ?'''
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (fecha, hora, link, descripcion, recordatorio_activo, recordatorio_minutos, id_evento))
        conn.commit()
        # print(f"Evento {id_evento} actualizado.")
        return True
    except Error as e:
        print(f"Error al actualizar evento {id_evento}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def eliminar_evento(id_evento):
    conn = crear_conexion()
    sql = 'DELETE FROM eventos WHERE id = ?'
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (id_evento,))
        conn.commit()
        # print(f"Evento {id_evento} eliminado.")
        return True
    except Error as e:
        print(f"Error al eliminar evento {id_evento}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def obtener_fechas_con_eventos():
    """Devuelve un set de fechas (str YYYY-MM-DD) que tienen al menos un evento."""
    conn = crear_conexion()
    fechas = set()
    sql = "SELECT DISTINCT fecha FROM eventos ORDER BY fecha"
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            fechas.add(row[0])
    except Error as e:
        print(f"Error al obtener fechas con eventos: {e}")
    finally:
        if conn:
            conn.close()
    return fechas
            
def obtener_evento_por_id(id_evento):
    """Obtiene todos los datos de un evento específico por su ID."""
    conn = crear_conexion()
    evento = None
    sql = "SELECT * FROM eventos WHERE id = ?"
    try:
        conn.row_factory = sqlite3.Row # Para acceder a las columnas por nombre
        cursor = conn.cursor()
        cursor.execute(sql, (id_evento,))
        row = cursor.fetchone()
        if row:
            evento = dict(row) # Convertir la fila en un diccionario
    except Error as e:
        print(f"Error al obtener evento por ID {id_evento}: {e}")
    finally:
        if conn:
            conn.close()
    return evento

# Llama a inicializar_db cuando este módulo se importe o ejecute por primera vez
if __name__ == "__main__":
    print("Inicializando base de datos...")
    inicializar_db()
    print("Base de datos lista.")
    # Ejemplo de uso (opcional, para probar)
    # agregar_evento('2024-08-15', '10:00', 'http://meet.google.com/abc', 'Audiencia Preliminar Caso X', 1, 30)
    # print(obtener_eventos_por_fecha('2024-08-15'))
    # print(obtener_todos_eventos_con_recordatorio())