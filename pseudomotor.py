import time
import requests
import json
import serial

class RobotController:
    """
    Clase que encapsula toda la lógica de movilidad del proyecto Caren.
    """
    def __init__(self):
        # --- Constantes y Configuración ---
        self.DATA_COLLECTION_URL = "http://127.0.0.1:5000/log"
        self.AI_PREDICTION_URL = "http://127.0.0.1:5000/predict" # URL futura para predicciones

        # --- Configuración del Puerto Serie ---
        self.SERIAL_PORT = '/dev/ttyUSB0' # Cambiar por el puerto correcto (ej. 'COM3' en Windows)
        self.BAUD_RATE = 115200
        self.ser = None
        # --- Estado del Robot ---
        self.entrenamiento_activado = False
        self.objetivo_actual = None
        self.latest_sensor_data = {} # Caché para los datos del puerto serie

        # --- Inicializar Conexión Serie ---
        try:
            self.ser = serial.Serial(self.SERIAL_PORT, self.BAUD_RATE, timeout=1)
            print(f"Conectado al puerto serie {self.SERIAL_PORT} a {self.BAUD_RATE} baudios.")
        except serial.SerialException as e:
            print(f"Error al abrir el puerto serie {self.SERIAL_PORT}: {e}")
            print("El robot funcionará con datos simulados.")

    # ===================================================================
    # FUNCIONES DE COMPROBACIÓN DE SISTEMAS (Simuladas)
    # ===================================================================

    def comprobar_script_entrenamiento(self):
        print("Comprobando script de registro de datos...")
        try:
            requests.get(self.DATA_COLLECTION_URL, timeout=1)
            return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return False

    def comprobar_modelo_ia_disponible(self):
        print(f"Comprobando si existe el modelo de IA en {self.RUTA_MODELO_IA}...")
        # En un futuro, esto podría comprobar si el servidor de predicción está activo
        return False # Por ahora, nos centramos en la recolección y movimiento por reglas

    # ===================================================================
    # ABSTRACCIÓN DE HARDWARE Y SENSORES (Simulada)
    # ===================================================================

    def ejecutar_movimiento(self, accion):
        """Envía el comando de acción al Arduino/ESP32 a través del puerto serie."""
        if self.ser and self.ser.is_open:
            print(f"MOTOR: Enviando comando '{accion}' al Arduino.")
            self.ser.write(f"{accion}\n".encode('utf-8'))
        else:
            print(f"MOTOR (Simulado): Ejecutando '{accion}' (Sin conexión serie)")

    def _read_and_cache_serial_data(self):
        """Lee una línea del ESP32, la parsea y la guarda en la caché."""
        if not self.ser or not self.ser.is_open:
            # Si no hay conexión serie, no hacemos nada. Las funciones usarán datos viejos o simulados.
            return

        try:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8').rstrip()
                if line:
                    self.latest_sensor_data = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Error al procesar datos del puerto serie: {e}")
        except serial.SerialException as e:
            print(f"Error de comunicación serie: {e}")
            self.ser.close()
            self.ser = None
    
    def leer_sensor_ultrasonidos(self, sensor):
        """Lee la distancia de un sensor de ultrasonidos desde la caché."""
        return self.latest_sensor_data.get('ultrasonidos', {}).get(sensor, 0.0)

    def capturar_imagen_actual(self):
        """Obtiene la imagen en formato Base64 desde la caché."""
        return self.latest_sensor_data.get('imagen_b64', "")

    def leer_brujula(self):
        """Lee la orientación de la brújula desde la caché."""
        # Se devuelve en un diccionario para mantener la compatibilidad con la IA
        # que esperaba 'posicion_visual'
        return {"orientacion": self.latest_sensor_data.get('brujula', 0.0)}

    # ===================================================================
    # COMUNICACIÓN CON IA
    # ===================================================================

    def predecir_accion_con_ia(self, estado_actual):
        """Placeholder para la predicción de la IA."""
        print("IA: Prediciendo acción (simulado)...")
        # En un futuro, esto haría una petición POST a self.AI_PREDICTION_URL
        return "DETENIDO" # Acción segura por defecto

    def enviar_a_script_entrenamiento(self, estado_completo, accion_tomada):
        """Envía el estado y la acción al servidor de recolección de datos."""
        print(f"REGISTRO: Enviando estado y acción '{accion_tomada}' al servidor...")
        try:
            payload = {
                "estado_completo": estado_completo,
                "accion_tomada": accion_tomada
            }
            # Se envía el payload como JSON. timeout para no bloquear el robot indefinidamente.
            response = requests.post(self.DATA_COLLECTION_URL, json=payload, timeout=2)
            if response.status_code != 200:
                print(f"REGISTRO: Error al enviar datos. Servidor respondió con {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"REGISTRO: No se pudo conectar con el servidor de datos. Error: {e}")

    # ===================================================================
    # FUNCIONES AUXILIARES Y DE LÓGICA
    # ===================================================================

    # ===================================================================
    # MODOS DE OPERACIÓN PRINCIPALES
    # ===================================================================

    def movimiento_controlado(self):
        print("\n--- MODO: MOVIMIENTO CONTROLADO ---")
        print("Esperando órdenes desde el servidor web...")
        while True:
            # Lógica para leer una pulsación web
            self._read_and_cache_serial_data() # Leemos para mantener la caché actualizada
            print("Leyendo pulsación web...")
            time.sleep(1)

    def movimiento_autonomo(self):
        print("\n--- MODO: MOVIMIENTO AUTÓNOMO (Solo Ultrasonidos) ---")
        intentos_fallidos = 0
        DIST_AVANCE = 30.0
        DIST_GIRO = 20.0

        while True:
            self._read_and_cache_serial_data()
            
            # Recopilar estado para posible envío
            estado_actual = self._recopilar_estado_completo()

            # Lógica de decisión basada en ultrasonidos
            dist_f = self.leer_sensor_ultrasonidos('frontal')
            accion_final = ""
            if dist_f > DIST_AVANCE:
                accion_final = "AVANZAR"
                intentos_fallidos = 0
            else:
                dist_r = self.leer_sensor_ultrasonidos('derecho')
                dist_l = self.leer_sensor_ultrasonidos('izquierdo')
                if dist_r > dist_l and dist_r > DIST_GIRO:
                    accion_final = "GIRAR_DERECHA"
                elif dist_l > DIST_GIRO:
                    accion_final = "GIRAR_IZQUIERDA"
                elif self.leer_sensor_ultrasonidos('trasero') > DIST_AVANCE:
                    accion_final = "RETROCEDER"
                else:
                    accion_final = "DETENIDO"
                    intentos_fallidos += 1
                    print(f"Atascado. Intento {intentos_fallidos}/5")
            
            # Enviar datos si el modo entrenamiento está activo
            if self.entrenamiento_activado:
                self.enviar_a_script_entrenamiento(estado_actual, accion_final)

            self.ejecutar_movimiento(accion_final)

            if intentos_fallidos >= 5:
                print("Atascado. Descansando 5 minutos...")
                self.ejecutar_movimiento("DETENIDO")
                time.sleep(300) # 5 minutos
                intentos_fallidos = 0
            time.sleep(0.1)

    def movimiento_con_IA(self):
        print("\n--- MODO: MOVIMIENTO CON IA (Puro) ---")
        while True:
            # Recopilar estado ya refresca los datos del puerto serie
            estado_actual = self._recopilar_estado_completo()
            accion_final = self.predecir_accion_con_ia(estado_actual)

            if self.entrenamiento_activado:
                self.enviar_a_script_entrenamiento(estado_actual, accion_final)
            
            self.ejecutar_movimiento(accion_final)
            time.sleep(0.1)

    def _recopilar_estado_completo(self):
        """
        Método interno para unificar la recolección de datos de sensores
        con la estructura que espera la IA.
        """
        return {
            "imagen_camara": self.capturar_imagen_actual(),
            "posicion_visual": self.leer_brujula(), # Contiene la 'orientacion'
            "distancias_ultra": {
                "frontal": self.leer_sensor_ultrasonidos('frontal'),
                "trasero": self.leer_sensor_ultrasonidos('trasero'),
                "derecho": self.leer_sensor_ultrasonidos('derecho'),
                "izquierdo": self.leer_sensor_ultrasonidos('izquierdo')
            }
        }

    # ===================================================================
    # LÓGICA DE ARRANQUE
    # ===================================================================

    def run(self):
        """
        Ejecuta las comprobaciones iniciales y lanza el modo de operación apropiado.
        """
        print("Iniciando sistema de movilidad de Caren...")
        
        self.entrenamiento_activado = self.comprobar_script_entrenamiento()

        print("\n--- Estado de los sistemas ---")
        print(f"Conexión Serie: {'OK' if self.ser and self.ser.is_open else 'ERROR'}")
        print(f"Modo Entrenamiento: {'ACTIVADO' if self.entrenamiento_activado else 'DESACTIVADO'}")
        print("----------------------------")

        # Decidir el modo de operación
        if self.ser and self.ser.is_open:
            self.movimiento_autonomo()
        else:
            self.movimiento_controlado()


if __name__ == "__main__":
    try:
        caren_robot = RobotController()
        caren_robot.run()
    except KeyboardInterrupt:
        print("\nApagando sistema de movilidad.")
        if caren_robot.ser and caren_robot.ser.is_open:
            caren_robot.ser.close()
        caren_robot.ejecutar_movimiento("DETENIDO")