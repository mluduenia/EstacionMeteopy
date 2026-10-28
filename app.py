from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# Configuración de la base de datos MySQL
DB_CONFIG = {
    'host': '10.0.10.220',
    'user': 'root',
    'password': 'neron123',
    'database': 'alert7'
}

# CONFIGURACIÓN DINÁMICA DEL INTERVALO (En milisegundos)
# 30 minutos = 30 * 60 * 1000 = 1800000 ms
# 1 hora     = 60 * 60 * 1000 = 3600000 ms
INTERVALO_REPORTE_MS = 1800000  # Modificá este valor cuando quieras sin re-grabar el Arduino

# =====================================================================
# FUNCIONES AUXILIARES PARA GUARDAR EN MYSQL
# =====================================================================

def guardar_temperatura(temp):
    """Inserta la temperatura en s1102_0."""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor()
            query = "INSERT INTO s1102_0 (T_TIME, T_DATA, valido, sumarizado) VALUES (NOW(), %s, 1, NULL)"
            cursor.execute(query, (temp,))
            connection.commit()
            print(f" -> [MySQL] Temperatura guardada en s1102_0: {temp} °C")
            return True
    except Error as e:
        print(f" -> [Error MySQL s1102_0]: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

def guardar_humedad(hum):
    """Inserta la humedad en s1101_0."""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor()
            query = "INSERT INTO s1101_0 (T_TIME, T_DATA, valido, sumarizado) VALUES (NOW(), %s, 1, NULL)"
            cursor.execute(query, (hum,))
            connection.commit()
            print(f" -> [MySQL] Humedad guardada en s1101_0: {hum} %")
            return True
    except Error as e:
        print(f" -> [Error MySQL s1101_0]: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

def guardar_lluvia(cont_actual):
    """Calcula la diferencia del contador y SIEMPRE inserta el registro en s1103_0."""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor()

            cursor.execute("SELECT T_DATA FROM s1103_0 ORDER BY T_TIME DESC LIMIT 1")
            ultimo_registro = cursor.fetchone()

            if ultimo_registro is not None:
                ultimo_cont = int(ultimo_registro[0])

                # Incremento normal
                if cont_actual >= ultimo_cont:
                    mm_caidos = cont_actual - ultimo_cont
                # Desborde circular (2047 a 0)
                elif ultimo_cont > 2000 and cont_actual < 50:
                    mm_caidos = (2048 - ultimo_cont) + cont_actual
                # Reinicio o anomalía
                else:
                    print(f" -> [Info MySQL] Se detectó reinicio de contador (Anterior: {ultimo_cont} | Nuevo: {cont_actual}).")
                    mm_caidos = 0
            else:
                mm_caidos = 0

            # Guardar SIEMPRE el valor del contador para auditoría
            query = "INSERT INTO s1103_0 (T_TIME, T_DATA, valido, sumarizado) VALUES (NOW(), %s, 1, NULL)"
            cursor.execute(query, (cont_actual,))
            connection.commit()

            if mm_caidos > 0:
                print(f" -> [MySQL s1103_0] ¡Lluvia registrada! Contador: {cont_actual} | Caído: {mm_caidos} mm")
            else:
                print(f" -> [MySQL s1103_0] Reporte guardado. Contador: {cont_actual} | Sin lluvia (0 mm)")
            return True

    except Error as e:
        print(f" -> [Error MySQL s1103_0]: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

def guardar_bateria(voltaje):
    """Inserta el voltaje de la batería en s1104_0."""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor()
            query = "INSERT INTO s1104_0 (T_TIME, T_DATA, valido, sumarizado) VALUES (NOW(), %s, 1, NULL)"
            cursor.execute(query, (voltaje,))
            connection.commit()
            print(f" -> [MySQL] Batería guardada en s1104_0: {voltaje} V")
            return True
    except Error as e:
        print(f" -> [Error MySQL s1104_0]: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# =====================================================================
# ENDPOINTS DE LA API (HTTP POST / GET)
# =====================================================================

@app.route('/api/sensor', methods=['POST'])
def recibir_datos():
    datos = request.get_json(force=True, silent=True)

    if not datos:
        raw_data = request.get_data(as_text=True)
        print(f"\n -> [DEBUG Error 400] Datos crudos recibidos: '{raw_data}'")
        return jsonify({"status": "error", "message": "JSON inválido o vacío"}), 400

    print(f"\n -> [Flask] Petición recibida desde {request.remote_addr}: {datos}")

    try:
        if 'lluvia_contador' in datos:
            cont_lluvia = int(datos.get('lluvia_contador'))
            guardar_lluvia(cont_lluvia)

        if 'temperatura' in datos and 'humedad' in datos:
            temp = float(datos.get('temperatura'))
            hum = float(datos.get('humedad'))
            guardar_temperatura(temp)
            guardar_humedad(hum)

        if 'bateria' in datos:
            v_bat = float(datos.get('bateria'))
            guardar_bateria(v_bat)

        # Devolvemos el intervalo configurado para que el Arduino actualice su reloj
        return jsonify({
            "status": "ok",
            "message": "Datos procesados con éxito",
            "intervalo_ms": INTERVALO_REPORTE_MS
        }), 200

    except (TypeError, ValueError) as e:
        print(f" -> [Error Parseo]: {e}")
        return jsonify({"status": "error", "message": f"Formato inválido: {str(e)}"}), 400

# =====================================================================
# INICIO DE LA APLICACIÓN
# =====================================================================

if __name__ == '__main__':
    print("=== SERVIDOR FLASK DE ESTACIÓN METEOROLÓGICA INICIADO ===")
    app.run(host='0.0.0.0', port=5000, debug=True)