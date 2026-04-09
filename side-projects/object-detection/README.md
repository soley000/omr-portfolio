# 🔍 Détection d'Objets – YOLOv8 · DETR · OWL-ViT

**Type : Side Project / Exploration Computer Vision**

---

## 🌞 Contexte et motivation

J'ai voulu découvrir concrètement les modèles de vision par ordinateur avant d'en croiser dans un contexte industriel.

Ce projet a évolué : j'ai commencé avec deux modèles classiques (YOLOv8 et SSD MobileNet), puis j'ai voulu explorer **ce que la recherche récente apporte réellement** — des architectures Transformer appliquées à la vision, et même la détection guidée par le langage naturel. L'objectif est toujours le même : charger des modèles pré-entraînés, les tester sur des images, observer les différences et comprendre les paradigmes derrière chaque approche.

---

## 🎯 Objectifs

- Expérimenter trois paradigmes de détection d'objets avec des modèles pré-entraînés
- Comprendre ce qui différencie un CNN classique, un Vision Transformer et un modèle open-vocabulary
- Construire une interface interactive pour visualiser les détections, ajuster les paramètres et comparer les modèles
- Documenter les observations de façon claire et reproductible

---

## 📸 Aperçu

### Résultats de détection

| YOLOv8n 🟥 | DETR ResNet-50 🟩 |
|:-----------:|:-----------------:|
| ![YOLOv8](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/object_detection_yolo.jpg) | ![DETR](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/object_detection_detr.jpg) |

| OWL-ViT 🟣 | Comparaison des 3 modèles |
|:----------:|:-----------:|
| ![OWLViT](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/object_detection_owlvit.jpg) | ![Comparaison](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/object_detection_comparaison.jpg) |

### Application interactive

| Un seul modèle | Comparaison côte à côte |
|:--------------:|:----------------------:|
| ![App single](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/object_detection_app_single.png) | ![App compare](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/object_detection_app_compare.png) |

---

## 🤖 Les trois modèles – pourquoi ce choix ?

Ils font tous la même chose en surface : **détecter des objets et les nommer sur une image**. Mais leur manière d'y arriver est fondamentalement différente, et c'est exactement ce qui les rend intéressants à comparer.

---

### 🟥 YOLOv8n — *Ultralytics, 2023*
**Paradigme : CNN one-stage**

YOLO (You Only Look Once) découpe l'image en grille et prédit en un seul passage toutes les boîtes et leurs labels. YOLOv8 est aujourd'hui **le standard industriel** de la détection temps réel — léger, rapide, utilisé en production partout (caméras de surveillance, robotique, tri automatique).

> Ce qu'il montre : la maîtrise du modèle de référence que l'on croise le plus en entreprise.

---

### 🟩 DETR ResNet-50 — *Meta AI (Facebook), 2020*
**Paradigme : Vision Transformer (Detection Transformer)**

DETR est le premier modèle à avoir appliqué l'architecture **Transformer** à la détection d'objets, en traitant la tâche comme un problème de séquence. Il supprime complètement le NMS (Non-Maximum Suppression) utilisé dans les CNN classiques — les boîtes englobantes émergent directement de l'attention entre les features de l'image.

> Ce qu'il montre : la compréhension de l'évolution des architectures deep learning, de CNN vers Transformer.

---

### 🟣 OWL-ViT — *Google Research, 2022*
**Paradigme : Open-Vocabulary Object Detection**

OWL-ViT (Vision Transformer for Open-World Localization) est un modèle **vision-langage** : au lieu d'être limité aux 80 classes COCO, il détecte ce qu'on lui décrit en texte libre — *"a red mug on a table"*, *"a person wearing a helmet"*. Il aligne les représentations visuelles et textuelles dans un espace commun (proche de CLIP), ce qui lui permet de généraliser sans réentraînement.

> Ce qu'il montre : la frontière entre vision et NLP, là où la recherche va aujourd'hui.

---

### Pourquoi ces trois ensemble ?

| Modèle | Année | Paradigme | Limites COCO ? | Point clé |
|--------|-------|-----------|----------------|-----------|
| YOLOv8n | 2023 | CNN one-stage | Oui (80 classes) | Vitesse, production |
| DETR ResNet-50 | 2020 | Vision Transformer | Oui (80 classes) | Architecture, précision |
| OWL-ViT | 2022 | Open-vocabulary | **Non** — texte libre | Flexibilité, généralisation |

Ensemble, ils couvrent l'évolution de la détection d'objets sur 5 ans : du CNN optimisé, au Transformer, jusqu'au modèle guidé par le langage.

---

## 📊 Observations

Résultats obtenus sur une scène intérieure chargée (table dressée, plantes, vases, livres, personne).

| Modèle | Objets détectés | Classes | Conf. moy. | Temps |
|--------|:--------------:|:-------:|:----------:|:-----:|
| YOLOv8n | 3 | 3 | 0.712 | 139 ms |
| DETR ResNet-50 | 9 | 6 | 0.896 | 1592 ms |
| OWL-ViT | variable | variable | ~0.6 | 989 ms |

**YOLOv8n** est le plus rapide (139 ms) mais détecte uniquement les objets les plus évidents — person, dining table, cup. Il passe à côté des éléments plus discrets.

**DETR ResNet-50** est le plus exhaustif : 9 objets, 6 classes dont book, potted plant et vase que YOLOv8 a manqués. Environ 11× plus lent — c'est le compromis précision/vitesse typique entre CNN et Transformer.

**OWL-ViT** illustre son paradigme open-vocabulary : il ne cherche que ce qu'on lui décrit en texte. Ses scores sont naturellement plus bas (seuil recommandé : 0.1), mais c'est le seul capable de détecter n'importe quel objet arbitraire sans réentraînement.

---

## 🛠️ Technologies utilisées

| Catégorie | Outils |
|-----------|--------|
| Langage | Python 3.10+ |
| Interface | Streamlit |
| Traitement d'image | OpenCV, PIL |
| Modèles | YOLOv8 (Ultralytics), DETR + OWL-ViT (Hugging Face 🤗) |
| Lancement Windows | `run_app.bat` |

---

## ⚙️ Fonctionnement de l'app

1. Upload d'une image (JPG ou PNG)
2. Choix du mode : **un seul modèle** ou **comparaison côte à côte**
3. Sélection du ou des modèles parmi YOLOv8, DETR, OWL-ViT
4. Pour OWL-ViT : saisie des objets à détecter en texte libre
5. Ajustement du seuil de confiance
6. Affichage des boîtes englobantes + métriques :
   - Nombre d'objets détectés
   - Classes uniques identifiées
   - Confiance moyenne et max
   - Temps d'inférence (ms)
7. Tableau comparatif + graphiques si mode comparaison
8. Téléchargement des images annotées

---

## 📁 Structure du projet

```
object-detection/
│
├── app/
│   └── app.py                        # Application Streamlit
│
├── data/
│   └── image_test.jpg                # Image de test
│
├── models/
│   └── yolov8n.pt                    # Poids YOLOv8n (téléchargés automatiquement)
│
├── results/
│   ├── resultat_yolov8.jpg
│   ├── resultat_detr.jpg
│   ├── resultat_owlvit.jpg
│   └── comparaison.jpg
│
├── notebooks/
│   └── object_detection_comparaison.ipynb
│
├── requirements.txt
├── run_app.bat
└── README.md
```

---

## 🚀 Lancer le projet

**1. Installer les dépendances**
```bash
pip install -r requirements.txt
```

**2. Lancer l'application**
```bash
streamlit run app/app.py
```

L'application s'ouvre sur `http://localhost:8501`.

> Sur Windows : double-cliquer sur `run_app.bat`.

---

## 📓 Notebook

[`notebooks/object_detection_comparaison.ipynb`](notebooks/object_detection_comparaison.ipynb) — exploration des trois modèles sur l'image test, visualisation des résultats et analyse comparative.

---

## 👩🏽‍💻 Auteure

**Rosette-Michèle Otounga**
Apprentie Big Data Engineering & Applied AI/ML
[LinkedIn](https://linkedin.com/in/rosette-michele) · [Portfolio](https://github.com/soley000/omr-portfolio)
