# Usar una imagen base de Python. La versión slim es más ligera.
FROM python:3.9-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema operativo
# - python3-tk: para la interfaz gráfica de video.py
# - libportaudio2: para sounddevice
# - espeak-ng: para el motor de voz offline pyttsx3
# - git: para instalar dependencias que lo requieran
# - curl: para descargar el instalador de Ollama
RUN apt-get update && apt-get install -y \
    python3-tk \
    libportaudio2 \
    espeak-ng \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copiar el archivo de requisitos primero para aprovechar el cache de Docker
COPY requirements.txt .

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todos los scripts de la aplicación al contenedor
COPY *.py ./
COPY *.sh ./

# Dar permisos de ejecución al script de inicio
RUN chmod +x /app/start.sh

# Comando que se ejecutará cuando el contenedor se inicie
CMD ["/app/start.sh"]
