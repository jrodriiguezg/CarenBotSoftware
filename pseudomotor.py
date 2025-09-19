import time
import math
import os
import random
import requests
import json

class RobotController:
    """
    Clase que encapsula toda la lógica de movilidad del proyecto Caren.
    """
    def __init__(self):
        # --- Constantes y Configuración ---
        self.DATA_COLLECTION_URL = "http://127.0.0.1:5000/log"
        self.AI_PREDICTION_URL = "http://127.0.0.1:5000/predict" # URL futura para predicciones
        self.RUTA_MODELO_IA = "models/caren_model.h5" # Ruta simulada

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

    def comprobar_si_hay_sensor(self):
        print("Comprobando sensores de ultrasonidos...")
        return True # Simulación: siempre OK

    def comprobar_si_hay_lidar(self):
        print("Comprobando sensor Lidar...")
        return True # Simulación: siempre OK

    def comprobar_si_hay_posicionamiento_visual(self):
        print("Comprobando script de posicionamiento visual...")
        return True # Simulación: siempre OK

    def comprobar_script_entrenamiento(self):
        print("Comprobando script de registro de datos...")
        try:
            # Intenta hacer una petición simple para ver si el servidor responde.
            # Un 405 (Method Not Allowed) en /log significa que el servidor está vivo.
            requests.get(self.DATA_COLLECTION_URL, timeout=1)
            return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return False

    def comprobar_modelo_ia_disponible(self):
        print(f"Comprobando si existe el modelo de IA en {self.RUTA_MODELO_IA}...")
        # return os.path.exists(self.RUTA_MODELO_IA)
        return True # Simulación: siempre disponible

    # ===================================================================
    # ABSTRACCIÓN DE HARDWARE Y SENSORES (Simulada)
    # ===================================================================

    def ejecutar_movimiento(self, accion):
        """Centraliza el control de los motores basado en la acción decidida."""
        print(f"MOTOR: Ejecutando '{accion}'")
        # Aquí iría el código GPIO para controlar los motores
        # Ejemplo:
        # if accion == "AVANZAR": self.mandar_senal_avance()
        # ...

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
                    # print("Datos recibidos del ESP32:", self.latest_sensor_data) # Descomentar para depurar
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Error al procesar datos del puerto serie: {e}")
        except serial.SerialException as e:
            print(f"Error de comunicación serie: {e}")
            self.ser.close()
            self.ser = None

    def leer_sensor_ultrasonidos(self, sensor):
        """Lee la distancia de un sensor de ultrasonidos desde la caché."""
        if self.ser:
            return self.latest_sensor_data.get('ultrasonidos', {}).get(sensor, 0.0)
        else: # Modo simulación si no hay puerto serie
            return random.uniform(5.0, 400.0)

    def leer_datos_completos_lidar(self):
        """Lee los datos del Lidar desde la caché."""
        if self.ser:
            return self.latest_sensor_data.get('lidar', [])
        else: # Modo simulación
            return [(angulo, random.uniform(10.0, 800.0)) for angulo in range(360)]

    def capturar_imagen_actual(self):
        """Obtiene la imagen en formato Base64 desde la caché."""
        if self.ser:
            return self.latest_sensor_data.get('imagen_b64', "")
        else: # Modo simulación
            return "" # Devolvemos un string vacío si no hay imagen

    def leer_datos_posicionamiento_visual(self):
        """Lee los datos de odometría visual desde la caché."""
        if self.ser:
            return self.latest_sensor_data.get('visual', {"x": 0, "y": 0, "orientacion": 0})
        else: # Modo simulación
            return {"x": random.uniform(0.0, 20.0), "y": random.uniform(0.0, 20.0), "orientacion": random.uniform(0.0, 359.9)}

    # ===================================================================
    # COMUNICACIÓN CON IA
    # ===================================================================

    def predecir_accion_con_ia(self, estado_actual):
        """Placeholder para la predicción de la IA."""
        # En el futuro, esto haría una petición POST a self.AI_PREDICTION_URL
        print("IA: Prediciendo acción (simulado)...")
        acciones_posibles = ["AVANZAR", "GIRAR_DERECHA", "GIRAR_IZQUIERDA", "RETROCEDER", "DETENIDO"]
        return random.choice(acciones_posibles)

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

    def obtener_coordenada_objetivo_desde_web(self):
        """Simula la obtención de un objetivo desde un servidor."""
        if not self.objetivo_actual:
            self.objetivo_actual = {"x": 15.0, "y": 18.0}
        print(f"Navegando hacia el objetivo: {self.objetivo_actual}")
        return self.objetivo_actual

    def encontrar_distancia_minima(self, datos_lidar, angulo_inicio, angulo_fin):
        """Encuentra la distancia mínima en un sector del Lidar."""
        # Normaliza los ángulos para que estén en el rango 0-359
        angulo_inicio = (angulo_inicio + 360) % 360
        angulo_fin = (angulo_fin + 360) % 360
        
        distancias_sector = []
        if angulo_inicio <= angulo_fin:
            for angulo, dist in datos_lidar[angulo_inicio:angulo_fin+1]:
                distancias_sector.append(dist)
        else: # El sector cruza el ángulo 0 (ej. de 315 a 45)
            for angulo, dist in datos_lidar[angulo_inicio:] + datos_lidar[:angulo_fin+1]:
                distancias_sector.append(dist)
        
        return min(distancias_sector) if distancias_sector else float('inf')

    def calcular_angulo(self, pos_origen, pos_destino):
        """Calcula el ángulo en grados desde el origen al destino."""
        delta_x = pos_destino['x'] - pos_origen['x']
        delta_y = pos_destino['y'] - pos_origen['y']
        return math.degrees(math.atan2(delta_y, delta_x))

    def distancia(self, pos_origen, pos_destino):
        """Calcula la distancia euclidiana entre dos puntos."""
        return math.sqrt((pos_destino['x'] - pos_origen['x'])**2 + (pos_destino['y'] - pos_origen['y'])**2)

    def resolver_obstaculos_locales_con_estado(self, estado):
        """Decide una acción segura basada solo en sensores de proximidad."""
        DISTANCIA_SEGURIDAD_ULTRA = 15.0  # cm
        
        dist_min_frontal = self.encontrar_distancia_minima(estado['datos_lidar'], -45, 45)
        dist_min_derecha = self.encontrar_distancia_minima(estado['datos_lidar'], -135, -45)
        dist_min_izquierda = self.encontrar_distancia_minima(estado['datos_lidar'], 45, 135)

        if dist_min_frontal > 50.0 and estado['distancias_ultra']['frontal'] > DISTANCIA_SEGURIDAD_ULTRA:
            return "AVANZAR"
        elif dist_min_derecha > dist_min_izquierda and dist_min_derecha > 40.0 and estado['distancias_ultra']['derecho'] > DISTANCIA_SEGURIDAD_ULTRA:
            return "GIRAR_DERECHA"
        elif dist_min_izquierda > 40.0 and estado['distancias_ultra']['izquierdo'] > DISTANCIA_SEGURIDAD_ULTRA:
            return "GIRAR_IZQUIERDA"
        elif estado['distancias_ultra']['trasero'] > DISTANCIA_SEGURIDAD_ULTRA:
            return "RETROCEDER"
        else:
            return "DETENIDO"

    # ===================================================================
    # MODOS DE OPERACIÓN PRINCIPALES
    # ===================================================================

    def movimiento_controlado(self):
        print("\n--- MODO: MOVIMIENTO CONTROLADO ---")
        print("Esperando órdenes desde el servidor web...")
        while True:
            # Lógica para leer una pulsación web
            self._read_and_cache_serial_data() # Leemos por si acaso, aunque no se use
            print("Leyendo pulsación web...")
            time.sleep(1)

    def movimiento_autonomo(self):
        print("\n--- MODO: MOVIMIENTO AUTÓNOMO (Solo Ultrasonidos) ---")
        intentos_fallidos = 0
        while True:
            self._read_and_cache_serial_data()
            dist_f = self.leer_sensor_ultrasonidos('frontal')
            if dist_f > 30.0:
                self.ejecutar_movimiento("AVANZAR")
                intentos_fallidos = 0
            else:
                self.ejecutar_movimiento("DETENIDO")
                dist_r = self.leer_sensor_ultrasonidos('derecho')
                dist_l = self.leer_sensor_ultrasonidos('izquierdo')
                if dist_r > dist_l and dist_r > 20.0:
                    self.ejecutar_movimiento("GIRAR_DERECHA")
                elif dist_l > 20.0:
                    self.ejecutar_movimiento("GIRAR_IZQUIERDA")
                elif self.leer_sensor_ultrasonidos('trasero') > 30.0:
                    self.ejecutar_movimiento("RETROCEDER")
                else:
                    intentos_fallidos += 1
                    print(f"Atascado. Intento {intentos_fallidos}/5")
            
            if intentos_fallidos >= 5:
                print("Atascado. Descansando 5 minutos...")
                self.ejecutar_movimiento("DETENIDO")
                time.sleep(300) # 5 minutos
                intentos_fallidos = 0
            
            time.sleep(0.2)

    def movimiento_autonomo_con_lidar(self):
        print("\n--- MODO: MOVIMIENTO AUTÓNOMO (Solo Lidar) ---")
        while True:
            self._read_and_cache_serial_data()
            datos_lidar = self.leer_datos_completos_lidar()
            dist_min_frontal = self.encontrar_distancia_minima(datos_lidar, -45, 45)
            
            if dist_min_frontal > 50.0:
                self.ejecutar_movimiento("AVANZAR")
            else:
                self.ejecutar_movimiento("DETENIDO")
                dist_min_derecha = self.encontrar_distancia_minima(datos_lidar, -135, -45)
                dist_min_izquierda = self.encontrar_distancia_minima(datos_lidar, 45, 135)
                if dist_min_derecha > dist_min_izquierda and dist_min_derecha > 40.0:
                    self.ejecutar_movimiento("GIRAR_DERECHA")
                elif dist_min_izquierda > 40.0:
                    self.ejecutar_movimiento("GIRAR_IZQUIERDA")
                else:
                    self.ejecutar_movimiento("RETROCEDER") # Simplificado
            time.sleep(0.2)

    def _recopilar_estado_completo(self):
        """Método interno para unificar la recolección de datos de sensores."""
        # Aseguramos que los datos de la caché están actualizados para este ciclo
        self._read_and_cache_serial_data()
        return {
            "imagen_camara": self.capturar_imagen_actual(),
            "posicion_visual": self.leer_datos_posicionamiento_visual(),
            "datos_lidar": self.leer_datos_completos_lidar(),
            "distancias_ultra": {
                "frontal": self.leer_sensor_ultrasonidos('frontal'),
                "trasero": self.leer_sensor_ultrasonidos('trasero'),
                "derecho": self.leer_sensor_ultrasonidos('derecho'),
                "izquierdo": self.leer_sensor_ultrasonidos('izquierdo')
            },
            "objetivo": self.obtener_coordenada_objetivo_desde_web()
        }

    def movimiento_autonomo_combinado(self):
        print("\n--- MODO: MOVIMIENTO AUTÓNOMO COMBINADO (Lidar + Ultrasonidos) ---")
        while True:
            self._read_and_cache_serial_data()
            estado_sensores = {
                "datos_lidar": self.leer_datos_completos_lidar(),
                "distancias_ultra": {
                    "frontal": self.leer_sensor_ultrasonidos('frontal'),
                    "trasero": self.leer_sensor_ultrasonidos('trasero'),
                    "derecho": self.leer_sensor_ultrasonidos('derecho'),
                    "izquierdo": self.leer_sensor_ultrasonidos('izquierdo')
                }
            }
            accion_final = self.resolver_obstaculos_locales_con_estado(estado_sensores)
            
            if self.entrenamiento_activado:
                # Para este modo, el estado no incluye ni objetivo ni posición visual
                self.enviar_a_script_entrenamiento(estado_sensores, accion_final)
            
            self.ejecutar_movimiento(accion_final)
            time.sleep(0.1)

    def navegacion_por_objetivos(self):
        print("\n--- MODO: NAVEGACIÓN POR OBJETIVOS (Reglas) ---")
        UMBRAL_ANGULO = 5.0 # grados
        UMBRAL_DISTANCIA = 0.2 # metros

        while True:
            # Recopilar estado ya refresca los datos del puerto serie
            estado_actual = self._recopilar_estado_completo()
            
            # Comprobar si hemos llegado
            if self.distancia(estado_actual['posicion_visual'], estado_actual['objetivo']) < UMBRAL_DISTANCIA:
                print("¡Objetivo alcanzado!")
                self.ejecutar_movimiento("DETENIDO")
                break

            # Capa baja: evasión de obstáculos
            accion_evasion = self.resolver_obstaculos_locales_con_estado(estado_actual)

            # Capa alta: planificación
            accion_final = ""
            if accion_evasion == "AVANZAR":
                angulo_hacia_objetivo = self.calcular_angulo(estado_actual['posicion_visual'], estado_actual['objetivo'])
                diferencia_angulo = (angulo_hacia_objetivo - estado_actual['posicion_visual']['orientacion'] + 180) % 360 - 180

                if abs(diferencia_angulo) > UMBRAL_ANGULO:
                    accion_final = "GIRAR_IZQUIERDA" if diferencia_angulo > 0 else "GIRAR_DERECHA"
                else:
                    accion_final = "AVANZAR"
            else:
                accion_final = accion_evasion # La evasión tiene prioridad

            if self.entrenamiento_activado:
                self.enviar_a_script_entrenamiento(estado_actual, accion_final)
            
            self.ejecutar_movimiento(accion_final)
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

    def movimiento_combinado_ia_sensores(self):
        print("\n--- MODO: MOVIMIENTO COMBINADO (IA + Sensores) ---")
        while True:
            # Recopilar estado ya refresca los datos del puerto serie
            estado_actual = self._recopilar_estado_completo()
            
            # La IA sugiere una acción
            accion_sugerida_ia = self.predecir_accion_con_ia(estado_actual)
            
            # Los sensores verifican la seguridad
            accion_segura_sensores = self.resolver_obstaculos_locales_con_estado(estado_actual)
            
            # Decisión final: la seguridad tiene prioridad
            accion_final = ""
            if accion_sugerida_ia == "AVANZAR" and accion_segura_sensores != "AVANZAR":
                print(f"SEGURIDAD: La IA quería AVANZAR, pero los sensores lo impiden. Ejecutando '{accion_segura_sensores}'")
                accion_final = accion_segura_sensores
            else:
                accion_final = accion_sugerida_ia
            
            if self.entrenamiento_activado:
                self.enviar_a_script_entrenamiento(estado_actual, accion_final)
            
            self.ejecutar_movimiento(accion_final)
            time.sleep(0.1)

    # ===================================================================
    # LÓGICA DE ARRANQUE
    # ===================================================================

    def run(self):
        """
        Ejecuta las comprobaciones iniciales y lanza el modo de operación apropiado.
        """
        print("Iniciando sistema de movilidad de Caren...")
        
        # Realizar comprobaciones
        lidar_ok = self.comprobar_si_hay_lidar()
        ultrasonidos_ok = self.comprobar_si_hay_sensor()
        visual_ok = self.comprobar_si_hay_posicionamiento_visual()
        modelo_ia_ok = self.comprobar_modelo_ia_disponible()
        self.entrenamiento_activado = self.comprobar_script_entrenamiento()

        print("\n--- Estado de los sistemas ---")
        print(f"Lidar: {'OK' if lidar_ok else 'ERROR'}")
        print(f"Ultrasonidos: {'OK' if ultrasonidos_ok else 'ERROR'}")
        print(f"Posicionamiento Visual: {'OK' if visual_ok else 'ERROR'}")
        print(f"Modelo IA: {'OK' if modelo_ia_ok else 'NO DISPONIBLE'}")
        print(f"Modo Entrenamiento: {'ACTIVADO' if self.entrenamiento_activado else 'DESACTIVADO'}")
        print("----------------------------")

        # Decidir el modo de operación
        if modelo_ia_ok and visual_ok and lidar_ok and ultrasonidos_ok:
            self.movimiento_combinado_ia_sensores()
        elif modelo_ia_ok:
            self.movimiento_con_IA()
        elif visual_ok and lidar_ok and ultrasonidos_ok:
            self.navegacion_por_objetivos()
        elif lidar_ok and ultrasonidos_ok:
            self.movimiento_autonomo_combinado()
        elif lidar_ok:
            self.movimiento_autonomo_con_lidar()
        elif ultrasonidos_ok:
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
        # Aquí podrías añadir una llamada para detener los motores de forma segura
        # caren_robot.ejecutar_movimiento("DETENIDO")