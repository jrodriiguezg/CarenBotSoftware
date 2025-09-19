import tkinter as tk
import sounddevice as sd
import numpy as np
import queue

# --- Configuración ---
DEVICE = None             # Dispositivo de audio (None para el predeterminado)
SAMPLERATE = 44100        # Muestras de audio por segundo
CHUNK_SIZE = 1024         # Número de muestras a leer a la vez
LINE_COLOR = "#66ff66"     # Color verde neón para el osciloscopio
BACKGROUND_COLOR = "#000000" # Fondo negro
AMPLIFICATION_FACTOR = 2.5  # Factor de amplificación (>1 para picos más grandes)
NOISE_GATE_THRESHOLD = 0.01 # Umbral de ruido más bajo para mayor sensibilidad


class AudioVisualizer:
    """
    Clase que gestiona la captura de audio y la visualización
    en una ventana de Tkinter.
    """
    def __init__(self, master):
        """
        Inicializa la ventana, el lienzo (canvas) y el stream de audio.
        """
        self.master = master
        self.master.title("Osciloscopio de Audio")

        # --- Configuración para Pantalla Completa ---
        self.master.attributes('-fullscreen', True)
        self.width = self.master.winfo_screenwidth()
        self.height = self.master.winfo_screenheight()
        # Permitir salir de pantalla completa con la tecla 'Esc'
        self.master.bind("<Escape>", self.toggle_fullscreen)

        self.master.configure(bg=BACKGROUND_COLOR)

        # Creamos un lienzo (canvas) para dibujar la forma de onda
        self.canvas = tk.Canvas(master, width=self.width, height=self.height, bg=BACKGROUND_COLOR, highlightthickness=0)
        self.canvas.pack()

        # La línea que representará la onda. La creamos una vez y luego solo actualizamos sus coordenadas.
        self.line = self.canvas.create_line(0, 0, 0, 0, fill=LINE_COLOR, width=1.5, tags="waveform")

        # Cola para comunicar de forma segura el hilo de audio con el hilo de la GUI
        self.audio_queue = queue.Queue()

        # Puntos en el eje X (horizontales). Son constantes, así que los precalculamos.
        self.x_coords = np.linspace(0, self.width, num=CHUNK_SIZE)

        try:
            # Iniciamos el stream de audio
            self.stream = sd.InputStream(
                device=DEVICE,
                channels=1,
                samplerate=SAMPLERATE,
                callback=self.audio_callback,
                blocksize=CHUNK_SIZE
            )
            self.stream.start()
            print("Stream de audio iniciado correctamente.")
        except Exception as e:
            print(f"Error al iniciar el stream de audio: {e}")
            print("Asegúrate de tener un micrófono conectado y los permisos necesarios.")
            # Mostramos un mensaje de error en la ventana
            self.canvas.create_text(
                self.width / 2, self.height / 2,
                text="Error: No se pudo acceder al micrófono.",
                fill="red", font=("Helvetica", 16)
            )
            return

        # Iniciamos el bucle de actualización de la pantalla
        self.update_plot()

    def toggle_fullscreen(self, event=None):
        """
        Activa o desactiva el modo de pantalla completa.
        """
        self.master.attributes("-fullscreen", not self.master.attributes("-fullscreen"))

    def audio_callback(self, indata, frames, time, status):
        """
        Esta función es llamada por sounddevice en un hilo separado cada vez
        que hay nuevos datos de audio disponibles.
        """
        if status:
            print(status)
        # Ponemos los datos del micrófono en la cola para que la GUI los procese
        self.audio_queue.put(indata[:, 0])

    def update_plot(self):
        """
        Actualiza el lienzo (canvas) con los nuevos datos de audio.
        """
        try:
            # Intentamos obtener datos de la cola sin bloquear el programa
            while not self.audio_queue.empty():
                data = self.audio_queue.get_nowait()

                # --- Puerta de Ruido (Noise Gate) ---
                # Calcula el volumen RMS (una medida de la potencia del sonido)
                volume = np.sqrt(np.mean(data**2))

                if volume < NOISE_GATE_THRESHOLD:
                    # Si el sonido es muy bajo, dibuja una línea casi plana
                    processed_data = np.zeros_like(data)
                else:
                    # --- Amplificación ---
                    # Amplifica la señal para picos más grandes
                    amplified_data = data * AMPLIFICATION_FACTOR
                    # Recorta la señal para que no se salga de la pantalla (crea picos planos)
                    processed_data = np.clip(amplified_data, -1.0, 1.0)

                # Escalamos los datos de audio (rango -1 a 1) a la altura de la ventana
                # El centro de la pantalla es la amplitud 0
                y_coords = (self.height / 2) * (1 - processed_data)

                # Combinamos las coordenadas X e Y en un formato que el canvas entiende: [x1, y1, x2, y2, ...]
                coords = np.column_stack((self.x_coords, y_coords)).flatten()

                # Actualizamos las coordenadas de la línea en lugar de borrarla y crearla de nuevo
                self.canvas.coords("waveform", *coords)

        except queue.Empty:
            # Si no hay datos, no hacemos nada
            pass
        finally:
            # Programamos la próxima actualización. Esto crea el bucle de animación.
            # 50 ms es aproximadamente 20 fotogramas por segundo (un poco más lento).
            self.master.after(50, self.update_plot)

    def on_closing(self):
        """
        Se ejecuta cuando el usuario cierra la ventana para detener el stream de audio.
        """
        print("Cerrando la aplicación...")
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        self.master.destroy()


if __name__ == "__main__":
    # Creamos la ventana principal de la aplicación
    root = tk.Tk()
    app = AudioVisualizer(root)

    # Asignamos la función de cierre para detener el audio de forma segura
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Iniciamos el bucle principal de la interfaz gráfica
    root.mainloop()