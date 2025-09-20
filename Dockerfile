# Usar una imagen base de Python sobre Debian 12 (Bookworm). La versión slim es más ligera.
FROM python:3.9-slim-bookworm

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema operativo
# - python3-tk: para la interfaz gráfica de video.py
# - libportaudio2: para sounddevice
# - espeak-ng: para el motor de voz offline pyttsx3
# - libpulse0: para una mejor compatibilidad de audio con PulseAudio/PipeWire
# - git: para instalar dependencias que lo requieran
# - curl: para descargar el instalador de Ollama
# - build-essential, pkg-config, libcairo2-dev: para compilar 'pycairo', una dependencia de 'playsound'.
# - libgirepository1.0-dev: para compilar 'pygobject', otra dependencia de 'playsound'.
# - portaudio19-dev: para compilar 'pyaudio', una dependencia de 'speechrecognition'.
# - gir1.2-gtk-3.0: Datos de introspección para PyGObject, usado por playsound en algunos sistemas.
# - xauth: para ayudar con la autorización de X11 para la interfaz gráfica.
# - python3-gi, python3-gi-cairo: Paquetes de sistema para PyGObject, para evitar errores de compilación con pip.
# - gstreamer1.0-plugins-good, gir1.2-gstreamer-1.0: Para que 'playsound' pueda reproducir audio (MP3, WAV).
# - alsa-utils: Provee 'aplay', una herramienta de reproducción de audio usada como fallback por 'pyttsx3'.
# - libasound2-plugins: Contiene el plugin para redirigir ALSA a PulseAudio.
RUN apt-get update && apt-get install -y \
    python3-tk \
    libportaudio2 \
    portaudio19-dev \
    espeak-ng \
    libpulse0 \
    git \
    curl \
    python3-gi \
    python3-gi-cairo \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    xauth \
    gir1.2-gtk-3.0 \
    gstreamer1.0-plugins-good \
    gir1.2-gstreamer-1.0 \
    libasound2-plugins \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Instalar Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copiar el archivo de requisitos primero para aprovechar el cache de Docker
COPY requirements.txt .

#Actualizar pip a la ultima version 
RUN pip install --upgrade pip

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorio para los modelos de voz de Piper y descargarlos
RUN mkdir -p /app/tts_models && \
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx" -o /app/tts_models/es_ES-sharvard-medium.onnx && \
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx.json" -o /app/tts_models/es_ES-sharvard-medium.onnx.json

# Copiar el archivo de configuración de ALSA para redirigir a PulseAudio
COPY asound.conf /etc/asound.conf

# Copiar todos los scripts de la aplicación al contenedor
COPY *.py ./
COPY *.sh ./

# Dar permisos de ejecución al script de inicio
RUN chmod +x /app/start.sh

# Comando que se ejecutará cuando el contenedor se inicie
CMD ["/app/start.sh"]
