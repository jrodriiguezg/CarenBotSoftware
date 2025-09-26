import os
import time
import base64
import io
import csv
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify

import tensorflow as tf
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense, Concatenate
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from PIL import Image


class AIModelManager:
    """
    Clase para recolectar datos, entrenar y usar la red neuronal de Tuppi.
    """
    def __init__(self, base_path="."):
        # --- Configuración de Rutas ---
        self.data_path = os.path.join(base_path, "data")
        self.images_path = os.path.join(self.data_path, "imagenes")
        self.models_path = os.path.join(base_path, "models")
        self.dataset_path = os.path.join(self.data_path, "CarenNano_dataset.csv")
        self.model_path = os.path.join(self.models_path, "carenNano_model.h5")

        # --- Configuración del Modelo ---
        self.image_dims = (64, 64, 3)  # Dimensiones de la imagen (alto, ancho, canales)
        self.num_lidar_points = 360
        self.actions = ["AVANZAR", "GIRAR_DERECHA", "GIRAR_IZQUIERDA", "RETROCEDER", "DETENIDO"]
        self.num_actions = len(self.actions)
        
        # --- Estado ---
        self.model = None
        self.label_encoder = None # Para convertir acciones de texto a números
        self.scaler = None # Para normalizar datos numéricos

        # Crear directorios si no existen
        os.makedirs(self.images_path, exist_ok=True)
        os.makedirs(self.models_path, exist_ok=True)

    # ===================================================================
    # PARTE 1: RECOLECCIÓN DE DATOS
    # ===================================================================

    def _flatten_data_for_csv(self, estado, accion, ruta_imagen):
        """Convierte el estado anidado en una lista plana para el CSV."""
        
        # Extraer solo las distancias del Lidar
        #lidar_distances = [dist for angulo, dist in estado['datos_lidar']]
        
        fila = [
            ruta_imagen,
            estado['posicion_visual']['x'],
            estado['posicion_visual']['y'],
            estado['posicion_visual']['orientacion'],
            #*lidar_distances,
            estado['distancias_ultra']['frontal'],
            estado['distancias_ultra']['derecho'],
            estado['distancias_ultra']['izquierdo'],
            estado['distancias_ultra']['trasero'],
            estado['objetivo']['x'],
            estado['objetivo']['y'],
            accion
        ]
        return fila

    def start_data_collection_server(self, host='0.0.0.0', port=5000):
        """Inicia un servidor Flask para recibir y guardar los datos de entrenamiento."""
        app = Flask(__name__)

        @app.route('/log', methods=['POST'])
        def log_data():
            data = request.json
            estado = data.get('estado_completo')
            accion = data.get('accion_tomada')

            if not estado or not accion:
                return jsonify({"status": "error", "message": "Datos incompletos"}), 400

            # La imagen viene como un string en base64. La decodificamos y guardamos.
            timestamp = int(time.time() * 1000)
            image_filename = f"img_{timestamp}.jpg"
            image_path = os.path.join(self.images_path, image_filename)
            
            image_b64 = estado.get('imagen_camara')
            if image_b64:
                image_data = base64.b64decode(image_b64)
                image = Image.open(io.BytesIO(image_data))
                image.save(image_path)

            # Aplanar y guardar en CSV
            csv_row = self._flatten_data_for_csv(estado, accion, image_path)
            
            # Crear cabecera si el archivo no existe
            if not os.path.exists(self.dataset_path):
                header = ['ruta_imagen', 'pos_x', 'pos_y', 'orientacion'] + \
                         [f'lidar_{i}' for i in range(self.num_lidar_points)] + \
                         ['ultra_f', 'ultra_d', 'ultra_i', 'ultra_t', 'obj_x', 'obj_y', 'accion']
                with open(self.dataset_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
            
            # Añadir la nueva fila
            with open(self.dataset_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(csv_row)

            return jsonify({"status": "success", "message": "Datos guardados"}), 200

        print(f"Servidor de recolección de datos iniciado en http://{host}:{port}")
        app.run(host=host, port=port)

    # ===================================================================
    # PARTE 2: ENTRENAMIENTO DEL MODELO
    # ===================================================================

    def _define_multimodal_architecture(self, num_numerical_features):
        """Define la arquitectura de la red neuronal multimodal usando Keras."""
        # RAMA 1: Procesador de Visión (CNN)
        image_input = tf.keras.layers.Input(shape=self.image_dims, name="entrada_imagen")
        x = tf.keras.layers.Conv2D(24, (5, 5), activation='relu')(image_input)
        x = tf.keras.layers.MaxPooling2D()(x)
        x = tf.keras.layers.Conv2D(36, (5, 5), activation='relu')(x)
        x = tf.keras.layers.MaxPooling2D()(x)
        x = tf.keras.layers.Flatten()(x)
        vision_output = tf.keras.layers.Dense(50, activation='relu')(x)

        # RAMA 2: Procesador de Datos Numéricos (MLP)
        numerical_input = tf.keras.layers.Input(shape=(num_numerical_features,), name="entrada_numerica")
        y = tf.keras.layers.Dense(64, activation='relu')(numerical_input)
        y = tf.keras.layers.Dense(32, activation='relu')(y)
        numerical_output = tf.keras.layers.Dense(16, activation='relu')(y)

        # FUSIÓN: Combinar las dos ramas
        combined = tf.keras.layers.Concatenate()([vision_output, numerical_output])

        # CABEZA: Capas finales para la toma de decisiones
        z = tf.keras.layers.Dense(100, activation='relu')(combined)
        z = tf.keras.layers.Dense(50, activation='relu')(z)
        output = tf.keras.layers.Dense(self.num_actions, activation='softmax', name="salida_accion")(z)

        # Crear y devolver el modelo final
        model = tf.keras.models.Model(inputs=[image_input, numerical_input], outputs=output)
        return model

    def train_model(self):
        """Carga el dataset, define y entrena el modelo de IA."""
        print("Iniciando proceso de entrenamiento...")
        
        # --- 1. Cargar y preparar los datos ---
        if not os.path.exists(self.dataset_path):
            print(f"Error: No se encuentra el archivo de dataset en {self.dataset_path}")
            return

        df = pd.read_csv(self.dataset_path)
        print(f"Dataset cargado. {len(df)} muestras encontradas.")

        # Separar características (X) y etiquetas (Y)
        y = df['accion']
        X = df.drop('accion', axis=1)

        # Codificar etiquetas de texto a números
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)
        y_categorical = to_categorical(y_encoded, num_classes=self.num_actions)

        # Separar características de imagen y numéricas
        X_image_paths = X['ruta_imagen']
        X_numerical = X.drop('ruta_imagen', axis=1)

        # Normalizar datos numéricos
        self.scaler = StandardScaler()
        X_numerical_scaled = self.scaler.fit_transform(X_numerical)

        # Dividir en conjuntos de entrenamiento y validación
        # (Se dividen los índices para mantener la correspondencia)
        indices = np.arange(len(df))
        train_indices, val_indices = train_test_split(indices, test_size=0.2, random_state=42)

        # --- 2. Crear un generador de datos para cargar imágenes bajo demanda ---
        # Esto es esencial para no agotar la memoria RAM con las imágenes
        def data_generator(image_paths, numerical_data, labels, indices, batch_size=32):
            num_samples = len(indices)
            while True:
                np.random.shuffle(indices)
                for offset in range(0, num_samples, batch_size):
                    batch_indices = indices[offset:offset+batch_size]
                    
                    batch_images = []
                    for i in batch_indices:
                        img_path = image_paths.iloc[i]
                        img = Image.open(img_path).resize(self.image_dims[:2])
                        batch_images.append(np.array(img) / 255.0)

                    batch_numerical = numerical_data[batch_indices]
                    batch_labels = labels[batch_indices]
                    
                    yield [np.array(batch_images), batch_numerical], batch_labels

        # --- 3. Definir, compilar y entrenar el modelo ---
        num_numerical_features = X_numerical_scaled.shape[1]
        self.model = self._define_multimodal_architecture(num_numerical_features)
        
        self.model.compile(optimizer='adam',
                           loss='categorical_crossentropy',
                           metrics=['accuracy'])
        
        print("Arquitectura del modelo:")
        self.model.summary()

        batch_size = 32
        train_gen = data_generator(X_image_paths, X_numerical_scaled, y_categorical, train_indices, batch_size)
        val_gen = data_generator(X_image_paths.values, X_numerical_scaled, y_categorical, val_indices, batch_size)

        print("\nIniciando entrenamiento...")
        self.model.fit(
            train_gen,
            steps_per_epoch=len(train_indices) // batch_size,
            validation_data=val_gen,
            validation_steps=len(val_indices) // batch_size,
            epochs=10 # Usar más épocas (ej. 50) en un caso real
        )

        # --- 4. Guardar el modelo entrenado ---
        self.model.save(self.model_path)
        print(f"\n¡Entrenamiento completado! Modelo guardado en {self.model_path}")

    # ===================================================================
    # PARTE 3: INFERENCIA (Uso en tiempo real)
    # ===================================================================

    def predict_action(self, estado_actual):
        """Carga el modelo y predice una acción basado en el estado actual."""
        if self.model is None:
            if os.path.exists(self.model_path):
                print(f"Cargando modelo desde {self.model_path}...")
                self.model = load_model(self.model_path)
                # Cargar también el encoder y el scaler guardados durante el entrenamiento
                # En un caso real, deberías guardar y cargar estos objetos con joblib o pickle
                print("Cargando modelo. (Simulando carga de encoder y scaler)")
            else:
                print("Error: Modelo no entrenado o no encontrado.")
                return "DETENIDO" # Acción segura por defecto

        # --- Preparar entradas para el modelo ---
        # 1. Imagen
        image_b64 = estado_actual.get('imagen_camara')
        if image_b64:
            image_data = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(image_data)).resize(self.image_dims[:2])
            img_processed = np.array(img) / 255.0
            img_processed = np.expand_dims(img_processed, axis=0) # Añadir dimensión de batch
        else:
            img_processed = np.zeros((1, *self.image_dims)) # Imagen negra si no hay datos

        # 2. Datos numéricos
        lidar_distances = [dist for angulo, dist in estado_actual['datos_lidar']]
        numerical_features = [
            estado_actual['posicion_visual']['x'],
            estado_actual['posicion_visual']['y'],
            estado_actual['posicion_visual']['orientacion'],
            *lidar_distances,
            estado_actual['distancias_ultra']['frontal'],
            estado_actual['distancias_ultra']['derecho'],
            estado_actual['distancias_ultra']['izquierdo'],
            estado_actual['distancias_ultra']['trasero'],
            estado_actual['objetivo']['x'],
            estado_actual['objetivo']['y'],
        ]
        # numerical_scaled = self.scaler.transform([numerical_features]) # Usar scaler entrenado en un caso real
        numerical_scaled = np.array([numerical_features]) # Simulación sin scaler

        # --- Realizar predicción ---
        prediction_probs = self.model.predict([img_processed, numerical_scaled])
        predicted_index = np.argmax(prediction_probs[0])
        
        # Convertir índice a acción de texto
        # predicted_action = self.label_encoder.inverse_transform([predicted_index])[0] # Usar en caso real
        predicted_action = self.actions[predicted_index] # Simulación

        print(f"IA: Predicción -> {predicted_action} (Confianza: {prediction_probs[0][predicted_index]:.2f})")
        return predicted_action


if __name__ == '__main__':
    import sys

    manager = AIModelManager()

    if len(sys.argv) > 1 and sys.argv[1] == 'train':
        # Para entrenar: python redIAutonoma.py train
        manager.train_model()
    elif len(sys.argv) > 1 and sys.argv[1] == 'collect':
        # Para recolectar datos: python redIAutonoma.py collect
        manager.start_data_collection_server()
    else:
        print("Uso:")
        print("  - Para recolectar datos: python redIAutonoma.py collect")
        print("  - Para entrenar el modelo: python redIAutonoma.py train")