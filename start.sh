#!/bin/bash

# Función para limpiar procesos en segundo plano al salir
cleanup() {
    echo "Deteniendo procesos en segundo plano..."
    if [ -n "$ollama_pid" ]; then
        kill $ollama_pid
    fi
    # Los otros scripts de python en segundo plano se detendrán cuando el contenedor muera.
    echo "Procesos detenidos."
}

# Capturar la señal de salida (cuando video.py se cierra) para ejecutar la limpieza
trap cleanup EXIT

# Iniciar el servidor de Ollama en segundo plano
echo "Iniciando servidor de Ollama..."
/usr/local/bin/ollama serve &
ollama_pid=$!

# Esperar a que Ollama esté listo y descargar el modelo
echo "Esperando a que Ollama esté disponible en http://127.0.0.1:11434..."
while ! curl -s --head http://127.0.0.1:11434 | head -n 1 | grep "200 OK" > /dev/null; do
    sleep 1
done
echo "Ollama está listo. Descargando/verificando el modelo gemma:2b (puede tardar la primera vez)..."
/usr/local/bin/ollama pull gemma:2b

# Iniciar el servidor de recolección de datos y la IA en segundo plano
echo "Iniciando servidor de IA (recolección)..."
python3 /app/redIAutonoma.py collect &

# Iniciar el asistente de voz en segundo plano
echo "Iniciando asistente de voz..."
python3 /app/ttsaudio.py &

# Iniciar el script de movilidad en segundo plano
echo "Iniciando control del robot..."
python3 /app/pseudomotor.py &

# Iniciar la interfaz gráfica en primer plano. El contenedor se mantendrá vivo mientras esta ventana esté abierta.
echo "Iniciando visualizador de audio..."
python3 /app/video.py