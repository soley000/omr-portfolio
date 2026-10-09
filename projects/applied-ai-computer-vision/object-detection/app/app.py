import streamlit as st
import cv2
import numpy as np
import time
import pandas as pd
from PIL import Image, ImageDraw
import io

# ─────────────────────────────────────────────
# Configuration de la page
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Détection d'objets – YOLOv8 · DETR · OWL-ViT",
    page_icon="🔍",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="metric-container"] {
    background: #0f0f1a;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("🔍 Détection d'Objets – YOLOv8 · DETR · OWL-ViT")
st.caption(
    "Comparaison de trois paradigmes de détection pré-entraînés sur COCO · "
    "CNN classique · Vision Transformer · Open-Vocabulary"
)

# ─────────────────────────────────────────────
# Chargement des modèles (mis en cache)
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner="⏳ Chargement de YOLOv8n…")
def load_yolo():
    from ultralytics import YOLO
    return YOLO("models/yolov8n.pt")

@st.cache_resource(show_spinner="⏳ Chargement de DETR ResNet-50…")
def load_detr():
    from transformers import DetrImageProcessor, DetrForObjectDetection
    processor = DetrImageProcessor.from_pretrained("facebook/detr-resnet-50")
    model = DetrForObjectDetection.from_pretrained("facebook/detr-resnet-50")
    return processor, model

@st.cache_resource(show_spinner="⏳ Chargement de OWL-ViT…")
def load_owlvit():
    from transformers import OwlViTProcessor, OwlViTForObjectDetection
    processor = OwlViTProcessor.from_pretrained("google/owlvit-base-patch32")
    model = OwlViTForObjectDetection.from_pretrained("google/owlvit-base-patch32")
    return processor, model

# ─────────────────────────────────────────────
# Fonctions utilitaires
# ─────────────────────────────────────────────
def _draw_label(img_bgr, text, x1, y1, color):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thick = 0.55, 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    y0 = max(y1 - 4, th + 6)
    cv2.rectangle(img_bgr, (x1, y0 - th - 5), (x1 + tw + 6, y0 + 3), color, -1)
    cv2.putText(img_bgr, text, (x1 + 3, y0 - 1), font, scale,
                (255, 255, 255), thick, cv2.LINE_AA)

def _build_stats(labels_list):
    if not labels_list:
        return {"nb_objets": 0, "classes_uniques": 0,
                "conf_moyenne": 0.0, "conf_max": 0.0, "classes": []}
    confs = [c for _, c in labels_list]
    classes = sorted({l for l, _ in labels_list})
    return {
        "nb_objets":       len(labels_list),
        "classes_uniques": len(classes),
        "conf_moyenne":    round(float(np.mean(confs)), 3),
        "conf_max":        round(float(np.max(confs)), 3),
        "classes":         classes,
    }

def image_to_bytes(img_rgb):
    pil = Image.fromarray(img_rgb)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()

# ─────────────────────────────────────────────
# Fonctions de détection
# ─────────────────────────────────────────────
def detect_yolo(image_bgr, seuil):
    """YOLOv8n – CNN one-stage, temps réel."""
    model = load_yolo()
    start = time.perf_counter()
    results = model(image_bgr, verbose=False)[0]
    duree_ms = (time.perf_counter() - start) * 1000

    img_out = image_bgr.copy()
    labels_list = []
    for box in results.boxes.data:
        if float(box[4]) < seuil:
            continue
        x1, y1, x2, y2, conf, cls = box[:6]
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        label = model.names[int(cls)]
        labels_list.append((label, float(conf)))
        cv2.rectangle(img_out, (x1, y1), (x2, y2), (30, 30, 220), 3)
        _draw_label(img_out, f"{label} {conf:.2f}", x1, y1, (30, 30, 220))

    return cv2.cvtColor(img_out, cv2.COLOR_BGR2RGB), _build_stats(labels_list), duree_ms


def detect_detr(image_bgr, seuil):
    """DETR ResNet-50 – Vision Transformer, sans NMS."""
    import torch
    processor, model = load_detr()
    h, w = image_bgr.shape[:2]
    img_pil = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))

    inputs = processor(images=img_pil, return_tensors="pt")
    start = time.perf_counter()
    with torch.no_grad():
        outputs = model(**inputs)
    duree_ms = (time.perf_counter() - start) * 1000

    target_sizes = torch.tensor([[h, w]])
    results = processor.post_process_object_detection(
        outputs, threshold=seuil, target_sizes=target_sizes
    )[0]

    img_out = image_bgr.copy()
    labels_list = []
    for score, label, box in zip(
        results["scores"].tolist(),
        results["labels"].tolist(),
        results["boxes"].tolist()
    ):
        x1, y1, x2, y2 = [int(v) for v in box]
        label_name = model.config.id2label[label]
        labels_list.append((label_name, float(score)))
        cv2.rectangle(img_out, (x1, y1), (x2, y2), (10, 200, 80), 3)
        _draw_label(img_out, f"{label_name} {score:.2f}", x1, y1, (10, 200, 80))

    return cv2.cvtColor(img_out, cv2.COLOR_BGR2RGB), _build_stats(labels_list), duree_ms


def detect_owlvit(image_bgr, seuil, texte_queries):
    """
    OWL-ViT – Open-vocabulary : détecte les objets décrits en texte libre.
    texte_queries : liste de strings, ex. ["a person", "a chair", "a dog"]
    """
    import torch
    processor, model = load_owlvit()
    h, w = image_bgr.shape[:2]
    img_pil = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))

    inputs = processor(text=[texte_queries], images=img_pil, return_tensors="pt")
    start = time.perf_counter()
    with torch.no_grad():
        outputs = model(**inputs)
    duree_ms = (time.perf_counter() - start) * 1000

    from transformers.models.owlvit.image_processing_owlvit import OwlViTImageProcessor
    _img_proc = OwlViTImageProcessor.from_pretrained("google/owlvit-base-patch32")
    target_sizes = torch.tensor([[h, w]], dtype=torch.float32)
    results = _img_proc.post_process_object_detection(
        outputs=outputs, threshold=seuil, target_sizes=target_sizes
    )[0]

    img_out = image_bgr.copy()
    labels_list = []
    for score, label, box in zip(
        results["scores"].tolist(),
        results["labels"].tolist(),
        results["boxes"].tolist()
    ):
        x1, y1, x2, y2 = [int(v) for v in box]
        label_name = texte_queries[label]
        labels_list.append((label_name, float(score)))
        cv2.rectangle(img_out, (x1, y1), (x2, y2), (200, 100, 255), 3)
        _draw_label(img_out, f"{label_name} {score:.2f}", x1, y1, (200, 100, 255))

    return cv2.cvtColor(img_out, cv2.COLOR_BGR2RGB), _build_stats(labels_list), duree_ms


def afficher_resultats(img_rgb, stats, duree_ms, nom_modele):
    """Affiche image annotée + 5 métriques + bouton téléchargement."""
    st.image(img_rgb, use_container_width=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🎯 Objets détectés",   stats["nb_objets"])
    c2.metric("🏷️ Classes uniques",   stats["classes_uniques"])
    c3.metric("📊 Confiance moyenne", f"{stats['conf_moyenne']:.2f}")
    c4.metric("🏆 Confiance max",     f"{stats['conf_max']:.2f}")
    c5.metric("⏱️ Inférence",         f"{duree_ms:.0f} ms")

    if stats["classes"]:
        st.markdown(f"**Objets identifiés :** {', '.join(stats['classes'])}")

    st.download_button(
        f"⬇️ Télécharger – {nom_modele}",
        data=image_to_bytes(img_rgb),
        file_name=f"resultat_{nom_modele.lower().replace(' ', '_')}.png",
        mime="image/png",
        key=f"dl_{nom_modele}_{id(img_rgb)}"
    )

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Paramètres")
    seuil = st.slider(
        "Seuil de confiance", 0.05, 1.0, 0.5, 0.05,
        help="Détections dont le score est inférieur à ce seuil sont ignorées"
    )
    mode = st.radio("Mode d'analyse", [
        "🔬 Un seul modèle",
        "⚖️ Comparaison côte à côte"
    ])
    st.divider()
    st.markdown("""
**Modèles disponibles**

🟥 **YOLOv8n** – Ultralytics  
CNN one-stage · temps réel

🟩 **DETR ResNet-50** – HuggingFace  
Vision Transformer · sans NMS

🟣 **OWL-ViT** – Google  
Open-vocabulary · détection par texte
""")
    st.divider()
    st.caption("Modèles mis en cache après le premier chargement.")

# ─────────────────────────────────────────────
# Upload image (image par défaut si rien chargé)
# ─────────────────────────────────────────────
DEFAULT_IMAGE = "data/image_test.jpg"

uploaded = st.file_uploader(
    "📁 Charger une image — ou laisse vide pour utiliser l'image de test",
    type=["jpg", "jpeg", "png"]
)

if uploaded is not None:
    file_bytes = np.frombuffer(uploaded.read(), np.uint8)
    image_bgr  = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    source_label = f"Image chargée : {uploaded.name}"
else:
    import os
    if not os.path.exists(DEFAULT_IMAGE):
        st.warning(
            f"Aucune image chargée et l'image par défaut `{DEFAULT_IMAGE}` est introuvable. "
            "Place une image dans `data/image_test.jpg` ou charge-en une."
        )
        st.stop()
    image_bgr    = cv2.imread(DEFAULT_IMAGE)
    source_label = f"Image par défaut : `{DEFAULT_IMAGE}`"

if image_bgr is None:
    st.error("❌ Impossible de lire l'image. Essaie un autre fichier JPG ou PNG.")
    st.stop()

h_img, w_img = image_bgr.shape[:2]
st.image(
    cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB),
    caption=f"{source_label} — {w_img} × {h_img} px",
    use_container_width=True
)
st.divider()

# ─────────────────────────────────────────────
# Session state — conserve les résultats après clic
# ─────────────────────────────────────────────
for key in ["res_single", "res_compare"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
MODELES = [
    "🟥 YOLOv8n",
    "🟩 DETR ResNet-50",
    "🟣 OWL-ViT (open-vocabulary)"
]

def run_model(choix, image_bgr, seuil, queries=None):
    if "YOLOv8" in choix:
        img, stats, dur = detect_yolo(image_bgr, seuil)
        return img, stats, dur, "YOLOv8n", "🟥"
    elif "DETR" in choix:
        img, stats, dur = detect_detr(image_bgr, seuil)
        return img, stats, dur, "DETR ResNet-50", "🟩"
    else:
        q = queries or ["person", "car", "chair", "bottle", "dog", "cat"]
        img, stats, dur = detect_owlvit(image_bgr, seuil, q)
        return img, stats, dur, "OWL-ViT", "🟣"

# ─────────────────────────────────────────────
# MODE 1 : Un seul modèle
# ─────────────────────────────────────────────
if mode == "🔬 Un seul modèle":
    choix = st.selectbox("Choisir un modèle", MODELES)

    queries = None
    if "OWL-ViT" in choix:
        st.info(
            "💡 **OWL-ViT** détecte ce que tu décris en texte libre. "
            "Entre les objets à rechercher, séparés par des virgules."
        )
        raw = st.text_input(
            "Objets à détecter",
            value="person, car, chair, bottle, dog, cat",
            placeholder="person, car, dog, laptop…"
        )
        queries = [q.strip() for q in raw.split(",") if q.strip()]

    if st.button("🚀 Lancer la détection", type="primary"):
        with st.spinner("Détection en cours…"):
            img_res, stats, duree, nom, badge = run_model(choix, image_bgr, seuil, queries)
        st.session_state["res_single"] = {
            "img": img_res, "stats": stats,
            "duree": duree, "nom": nom, "badge": badge
        }

    if st.session_state["res_single"]:
        r = st.session_state["res_single"]
        st.subheader(f"{r['badge']} Résultats – {r['nom']}")
        afficher_resultats(r["img"], r["stats"], r["duree"], r["nom"])

# ─────────────────────────────────────────────
# MODE 2 : Comparaison côte à côte
# ─────────────────────────────────────────────
else:
    cs1, cs2 = st.columns(2)
    choix1 = cs1.selectbox("Modèle A", MODELES, index=0, key="sel1")
    choix2 = cs2.selectbox("Modèle B", MODELES, index=1, key="sel2")

    queries1 = queries2 = None

    if "OWL-ViT" in choix1:
        raw1 = cs1.text_input("Requêtes texte – Modèle A",
                               value="person, car, chair, bottle, dog",
                               key="q1")
        queries1 = [q.strip() for q in raw1.split(",") if q.strip()]

    if "OWL-ViT" in choix2:
        raw2 = cs2.text_input("Requêtes texte – Modèle B",
                               value="person, car, chair, bottle, dog",
                               key="q2")
        queries2 = [q.strip() for q in raw2.split(",") if q.strip()]

    if st.button("⚖️ Lancer la comparaison", type="primary"):
        c1, c2 = st.columns(2)
        with c1:
            with st.spinner(f"{choix1}…"):
                r1 = run_model(choix1, image_bgr, seuil, queries1)
        with c2:
            with st.spinner(f"{choix2}…"):
                r2 = run_model(choix2, image_bgr, seuil, queries2)

        st.session_state["res_compare"] = {
            "img1": r1[0], "stats1": r1[1], "dur1": r1[2], "nom1": r1[3], "badge1": r1[4],
            "img2": r2[0], "stats2": r2[1], "dur2": r2[2], "nom2": r2[3], "badge2": r2[4],
        }

    if st.session_state["res_compare"]:
        r = st.session_state["res_compare"]
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"{r['badge1']} {r['nom1']}")
            afficher_resultats(r["img1"], r["stats1"], r["dur1"], r["nom1"])

        with col2:
            st.subheader(f"{r['badge2']} {r['nom2']}")
            afficher_resultats(r["img2"], r["stats2"], r["dur2"], r["nom2"])

        st.divider()
        st.subheader("📊 Tableau comparatif")
        df = pd.DataFrame({
            "Métrique": [
                "Objets détectés", "Classes uniques",
                "Confiance moyenne", "Confiance max",
                "Temps d'inférence (ms)", "Objets identifiés"
            ],
            r["nom1"]: [
                r["stats1"]["nb_objets"], r["stats1"]["classes_uniques"],
                f"{r['stats1']['conf_moyenne']:.3f}", f"{r['stats1']['conf_max']:.3f}",
                f"{r['dur1']:.0f} ms",
                ", ".join(r["stats1"]["classes"]) or "—"
            ],
            r["nom2"]: [
                r["stats2"]["nb_objets"], r["stats2"]["classes_uniques"],
                f"{r['stats2']['conf_moyenne']:.3f}", f"{r['stats2']['conf_max']:.3f}",
                f"{r['dur2']:.0f} ms",
                ", ".join(r["stats2"]["classes"]) or "—"
            ],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

        g1, g2 = st.columns(2)
        with g1:
            st.subheader("⏱️ Temps d'inférence (ms)")
            st.bar_chart(pd.DataFrame({
                "Modèle": [r["nom1"], r["nom2"]],
                "ms":     [round(r["dur1"]), round(r["dur2"])]
            }).set_index("Modèle"))
        with g2:
            st.subheader("🎯 Objets détectés")
            st.bar_chart(pd.DataFrame({
                "Modèle": [r["nom1"], r["nom2"]],
                "Objets": [r["stats1"]["nb_objets"], r["stats2"]["nb_objets"]]
            }).set_index("Modèle"))
