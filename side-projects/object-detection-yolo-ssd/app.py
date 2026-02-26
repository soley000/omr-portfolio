import streamlit as st
import cv2
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from ultralytics import YOLO
import tempfile
import time
from PIL import Image

st.set_page_config(page_title="Détection d'Objets", layout="centered")

st.title(" Détection d'Objets – Projet M1")
st.markdown("Choisissez un modèle, importez une image, ajustez le seuil, et observez les résultats.")

model_choice = st.selectbox("🔍 Choisir un modèle", ["YOLOv8", "SSD MobileNet"])
seuil_confiance = st.slider("🎚️ Seuil de confiance", 0.0, 1.0, 0.5, 0.05)
uploaded_file = st.file_uploader("📸 Importer une image", type=["jpg", "jpeg", "png"])

def detect_yolo(image_bgr):
    model = YOLO("yolov8n.pt")
    results = model(image_bgr)[0]
    image_out = image_bgr.copy()
    for box in results.boxes.data:
        x1, y1, x2, y2, conf, cls = box[:6]
        if conf < seuil_confiance:
            continue
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        label = model.names[int(cls)]
        cv2.rectangle(image_out, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(image_out, f"{label} {conf:.2f}", (x1, max(y1 - 10, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    return image_out

def detect_ssd(image_bgr):
    model = hub.load("https://tfhub.dev/tensorflow/ssd_mobilenet_v2/2")
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image_tf = tf.convert_to_tensor(image_rgb, dtype=tf.uint8)
    image_resized = tf.image.resize_with_pad(image_tf, 320, 320)
    image_input = tf.expand_dims(tf.cast(image_resized, tf.uint8), axis=0)
    results = model(image_input)

    boxes = results["detection_boxes"].numpy()[0]
    scores = results["detection_scores"].numpy()[0]
    classes = results["detection_classes"].numpy()[0].astype(int)

    image_out = image_bgr.copy()
    h, w, _ = image_out.shape
    for i in range(len(scores)):
        if scores[i] >= seuil_confiance:
            y1, x1, y2, x2 = boxes[i]
            x1, y1, x2, y2 = int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
            label = f"Classe {classes[i]}"
            cv2.rectangle(image_out, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(image_out, f"{label} {scores[i]:.2f}", (x1, max(y1 - 10, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return image_out

if uploaded_file:
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    image_bgr = cv2.imdecode(file_bytes, 1)

    st.image(image_bgr, caption="🖼️ Image d'origine", use_column_width=True)

    with st.spinner("🔍 Détection en cours..."):
        start = time.time()
        if model_choice == "YOLOv8":
            image_detected = detect_yolo(image_bgr)
        else:
            image_detected = detect_ssd(image_bgr)
        duration = time.time() - start

    st.success(f"✅ Détection terminée en {duration:.2f} secondes")
    st.image(image_detected, caption=f"📌 Résultat – {model_choice}", use_column_width=True)

    result_pil = Image.fromarray(cv2.cvtColor(image_detected, cv2.COLOR_BGR2RGB))
    buf = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    result_pil.save(buf.name)
    with open(buf.name, "rb") as f:
        st.download_button("📥 Télécharger le résultat", f, file_name="resultat_detection.jpg")
