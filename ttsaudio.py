import speech_recognition as sr
import pyttsx3
import requests
import json
import os
import time
try:
    from piper.config import PiperConfig
    from piper.voice import PiperVoice
    import wave
except ImportError:
    PiperVoice = None

try:
    from gtts import gTTS
    from playsound import playsound
    import tempfile
except ImportError:
    gTTS = None
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- Configuración ---
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
#OLLAMA_MODEL = "karen-finetuned"  # ¡Tu modelo personalizado!
OLLAMA_MODEL = "gemma:2b"  # Modelo más ligero, ideal para Raspberry Pi. Descargar con 'ollama pull gemma:2b'
MEMORY_FILE = "memory.json"
TRAINING_LOG_FILE = "training_log.jsonl" # Archivo para guardar conversaciones para futuro entrenamiento
WAKE_WORD = "karen"  # Palabra para activar al asistente (en minúsculas)
WHISPER_MODEL = "small" # 'tiny', 'base', 'small', 'medium'. 'small' es un buen equilibrio. 'medium' puede consumir demasiada RAM.
CONVERSATION_TIMEOUT = 30 # Segundos de inactividad antes de salir del modo conversación

# --- Configuración para TTS Local de Alta Calidad (Piper) ---
PIPER_VOICE_ONNX = "tts_models/es_ES-sharvard-medium.onnx"
PIPER_VOICE_JSON = "tts_models/es_ES-sharvard-medium.onnx.json"

# --- Configuración para IA Online (Opcional) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Obtiene la clave de una variable de entorno

def check_internet_connection(url='http://www.google.com/', timeout=3):
    """Verifica si hay conexión a internet intentando acceder a una URL."""
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

class TextToSpeech:
    """
    Gestiona la síntesis de voz.
    Prioriza un motor online de alta calidad (gTTS) si hay internet.
    Si no, utiliza un motor offline de respaldo (pyttsx3).
    """
    def __init__(self):
        self.piper_voice = self._init_piper_engine()
        self.offline_engine = self._init_offline_engine()
        if not gTTS:
            print("Advertencia: La librería 'gTTS' no está instalada. Solo se usará la voz offline.")

    def _init_piper_engine(self):
        """Inicializa el motor de voz local de alta calidad (Piper)."""
        if not PiperVoice:
            print("Advertencia: La librería 'piper-tts' no está instalada. No se usará la voz local de alta calidad.")
            return None
        
        if not os.path.exists(PIPER_VOICE_ONNX):
            print(f"Advertencia: No se encuentra el modelo de voz de Piper en '{PIPER_VOICE_ONNX}'.")
            print("Asegúrate de haberlo descargado en la carpeta 'tts_models'.")
            return None
        
        try:
            print("Cargando motor de voz local (Piper)...")
            voice = PiperVoice.from_files(PIPER_VOICE_ONNX, PIPER_VOICE_JSON)
            print("Motor de voz Piper cargado correctamente.")
            return voice
        except Exception as e:
            print(f"Error al cargar el motor de voz Piper: {e}")
            return None

    def _init_offline_engine(self):
        """Inicializa el motor de voz offline (pyttsx3) como respaldo."""
        try:
            engine = pyttsx3.init()
            # Intenta encontrar y configurar una voz en español
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'spanish' in voice.name.lower() or 'es-es' in voice.id.lower() or (hasattr(voice, 'lang') and 'es' in voice.lang):
                    engine.setProperty('voice', voice.id)
                    print(f"Motor offline: Usando voz en español '{voice.name}'")
                    break
            engine.setProperty('rate', 160)
            return engine
        except Exception as e:
            print(f"Error al inicializar el motor de TTS offline (pyttsx3): {e}")
            print("Esto puede ocurrir si no tienes un motor de TTS instalado en tu sistema.")
            print("En sistemas Debian/Ubuntu, prueba con: sudo apt-get install espeak-ng")
            return None

    def speak(self, text):
        """Convierte un texto a voz."""
        if not text:
            print("Asistente: (Nada que decir)")
            return

        print(f"Asistente: {text}")

        # Prioridad 1: Usar Piper (local, rápido, alta calidad)
        if self.piper_voice:
            try:
                with tempfile.NamedTemporaryFile(delete=True, suffix='.wav') as fp:
                    with wave.open(fp.name, 'wb') as wav_file:
                        self.piper_voice.synthesize(text, wav_file)
                    playsound(fp.name)
                return # Éxito
            except Exception as e:
                print(f"Error con el TTS local (Piper): {e}. Intentando con el siguiente motor.")

        # Prioridad 2: Usar gTTS (online, alta calidad) si Piper falla
        if gTTS and check_internet_connection():
            try:
                tts = gTTS(text=text, lang='es', slow=False)
                with tempfile.NamedTemporaryFile(delete=True, suffix='.mp3') as fp:
                    tts.save(fp.name)
                    playsound(fp.name)
                return # Éxito
            except Exception as e:
                print(f"Error con el TTS online (gTTS): {e}. Usando motor offline de respaldo.")
        
        # Prioridad 3: Usar pyttsx3 (offline, baja calidad) como último recurso
        if self.offline_engine:
            self.offline_engine.say(text)
            self.offline_engine.runAndWait()
        else:
            print("Error: No hay ningún motor de TTS disponible.")

class MemoryManager:
    """Gestiona la memoria a largo plazo del asistente en un archivo JSON."""
    def __init__(self, filepath):
        self.filepath = filepath
        self.memory = self._load_memory()

    def _load_memory(self):
        """Carga la memoria desde el archivo JSON."""
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_memory(self):
        """Guarda la memoria en el archivo JSON."""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, indent=4, ensure_ascii=False)

    def remember(self, key, value):
        """Añade un nuevo hecho a la memoria."""
        self.memory[key.lower()] = value
        self._save_memory()
        print(f"Memoria: He recordado que '{key}' es '{value}'")

    def retrieve_context(self, text):
        """Busca en la memoria hechos relevantes para el texto dado."""
        context = ""
        for key, value in self.memory.items():
            if key in text.lower():
                context += f"Dato relevante: {key} es {value}. "
        return context

class Assistant:
    """El asistente personal que escucha, piensa y habla."""
    def __init__(self):
        print("Inicializando asistente...")
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.recognizer.pause_threshold = 1.2 # Segundos de silencio para considerar que la frase ha terminado.
        self.tts = TextToSpeech()
        self.memory = MemoryManager(MEMORY_FILE)
        self.running = True  # Flag para controlar el bucle principal

        # Diccionario de comandos para una fácil expansión
        self.commands = {
            "recuerda que": self.command_remember,
            "qué sabes sobre": self.command_retrieve_memory,
            "qué hora es": self.command_get_time,
        }

        # Ajuste de energía para el ruido ambiental
        with self.microphone as source:
            print("Calibrando micrófono, por favor, guarda silencio...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        print("Calibración finalizada.")

    def listen(self, conversation_mode=False):
        """Escucha la voz del usuario a través del micrófono."""
        with self.microphone as source:
            # Ajusta el prompt y el timeout según el modo
            if conversation_mode:
                listen_timeout = 10  # Segundos de timeout en modo conversación
                print(f"Escuchando... (timeout en {listen_timeout}s)")
            else:
                listen_timeout = None  # Espera indefinidamente la palabra de activación
                print("Esperando palabra de activación...")

            try:
                # Escuchamos por más tiempo para capturar frases más largas
                audio = self.recognizer.listen(source, timeout=listen_timeout, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                return "" # Ocurrió un timeout, devuelve un string vacío

        try:
            # Usa un modelo de Whisper más grande para mayor precisión
            text = self.recognizer.recognize_whisper(audio, language="es", model=WHISPER_MODEL)
            # Solo imprimimos si se ha detectado algo para no llenar la consola
            if text:
                print(f"Usuario dijo: {text}")
            return text.lower()
        except sr.UnknownValueError:
            print("No he podido entender lo que has dicho.")
            return ""
        except sr.RequestError as e:
            print(f"Error en el servicio de reconocimiento; {e}")
            return ""

    def query_llm(self, prompt, context=""):
        """Envía una consulta al modelo de IA local (Ollama)."""
        full_prompt = f"Contexto: {context}\n\nPregunta: {prompt}\n\nRespuesta:"
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False,
            "system": "Eres un asistente de IA llamado Karen. Respondes en español de forma breve y directa."
        }
        try:
            response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=60)
            response.raise_for_status()
            response_data = response.json()
            return response_data.get("response", "Lo siento, no he podido generar una respuesta.").strip()
        except requests.exceptions.RequestException as e:
            return f"Error al conectar con el modelo de IA: {e}"

    def query_gemini(self, prompt, context=""):
        """Envía una consulta a la API de Gemini como fallback."""
        if not genai:
            return "La librería de Google no está instalada. No se puede usar Gemini."
        if not GEMINI_API_KEY:
            return "La clave de API de Gemini no está configurada."

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            
            full_prompt = f"Contexto: {context}\n\nPregunta: {prompt}\n\nResponde en español de forma concisa."
            
            response = model.generate_content(full_prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error al contactar con Gemini: {e}"

    # --- Definición de Habilidades/Comandos ---

    def command_remember(self, argument):
        """Comando para guardar un hecho en la memoria."""
        try:
            key, value = argument.split(" es ", 1)
            self.memory.remember(key, value)
            self.tts.speak(f"Entendido. He recordado que {key} es {value}.")
        except ValueError:
            self.tts.speak("No he entendido el formato. Por favor, usa 'recuerda que [algo] es [su valor]'.")

    def command_retrieve_memory(self, argument):
        """Comando para recuperar un hecho de la memoria."""
        context = self.memory.retrieve_context(argument)
        if context:
            self.tts.speak(context)
        else:
            self.tts.speak(f"No tengo recuerdos sobre {argument}.")

    def command_get_time(self, argument):
        """Comando para decir la hora actual."""
        now = time.localtime()
        current_time = time.strftime("%I:%M %p", now)
        self.tts.speak(f"Son las {current_time}.")

    def command_shutdown(self):
        """Comando para apagar el asistente."""
        self.tts.speak("Hasta luego. Apagándome.")
        self.running = False

    def command_general_query(self, prompt):
        """Maneja cualquier otra consulta enviándola al LLM."""
        # --- Lógica de consulta con fallback ---
        self.tts.speak("Pensando...")
        context = self.memory.retrieve_context(prompt)
        final_response = ""
        response_was_good = False
        
        # 1. Intentar con el modelo local (Ollama)
        local_response = self.query_llm(prompt, context)
        
        # 2. Evaluar si la respuesta local es insatisfactoria
        is_local_response_poor = (
            "error al conectar" in local_response.lower() or
            "no he podido generar una respuesta" in local_response.lower() or
            "no sé" in local_response.lower()
        )

        if not is_local_response_poor:
            # La respuesta local es buena, la usamos.
            final_response = local_response
            response_was_good = True
        else:
            # 3. La respuesta local no es buena, intentamos con el modelo online (Gemini)
            self.tts.speak("La respuesta local no fue clara. Consultando online...")
            if check_internet_connection():
                online_response = self.query_gemini(prompt, context)
                final_response = online_response
                # Asumimos que la respuesta online es buena si no contiene un error
                if "error" not in online_response.lower():
                    response_was_good = True
            else:
                self.tts.speak("No hay conexión a internet. Usaré la respuesta local.")
                final_response = local_response # Damos la respuesta local mala como último recurso.
        
        self.tts.speak(final_response)
        if response_was_good:
            self.log_interaction_for_training(prompt, final_response)

    def log_interaction_for_training(self, prompt, response):
        """Guarda la interacción en un archivo para futuro fine-tuning."""
        try:
            with open(TRAINING_LOG_FILE, 'a', encoding='utf-8') as f:
                log_entry = {"prompt": prompt, "response": response}
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error al guardar el log de entrenamiento: {e}")

    def process_command(self, command):
        """Procesa el comando del usuario y decide qué hacer."""
        # Comandos de apagado tienen prioridad
        if command in ["apágate", "adiós"]:
            self.command_shutdown()
            return

        # Itera sobre el diccionario de comandos
        for keyword, function in self.commands.items():
            if command.startswith(keyword):
                argument = command.replace(keyword, "", 1).strip()
                function(argument)
                return  # Termina después de ejecutar el comando

        # Si no coincide con ningún comando, es una pregunta general
        self.command_general_query(command)

    def run(self):
        """Bucle principal del asistente."""
        self.tts.speak("Asistente personal iniciado. Di mi nombre para activarme.")
        
        while self.running:
            # 1. Espera la palabra de activación
            command = self.listen()
            if WAKE_WORD in command:
                self.tts.speak("Sí, dime.")
                
                # Procesa el resto del comando si se dijo junto con la palabra de activación
                prompt = command.replace(WAKE_WORD, "", 1).strip()
                if prompt:
                    self.process_command(prompt)

                # 2. Entra en modo conversación
                last_interaction_time = time.time()
                while self.running:
                    # Comprueba el timeout por inactividad
                    if time.time() - last_interaction_time > CONVERSATION_TIMEOUT:
                        self.tts.speak("Volviendo a modo de espera por inactividad.")
                        break # Sale del bucle de conversación

                    # Escucha el siguiente comando
                    conversation_command = self.listen(conversation_mode=True)
                    if conversation_command:
                        last_interaction_time = time.time() # Reinicia el temporizador
                        
                        # Comprueba si el usuario quiere terminar la conversación
                        if conversation_command in ["gracias", "eso es todo", "para", "adiós", "apágate"]:
                            self.command_shutdown() if conversation_command in ["adiós", "apágate"] else self.tts.speak("De acuerdo. Quedo a la espera.")
                            break # Sale del bucle de conversación
                        
                        self.process_command(conversation_command)

if __name__ == "__main__":
    try:
        assistant = Assistant()
        assistant.run()
    except Exception as e:
        print(f"Ha ocurrido un error fatal: {e}")
    finally:
        print("Programa finalizado.")
