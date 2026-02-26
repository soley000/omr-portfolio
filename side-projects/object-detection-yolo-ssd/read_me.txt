Parfait, Omr 😎 ! On va fusionner les deux versions, garder **ta voix, la motivation honnête**, la structure claire, mais sans inventer de chiffres ou de durée. On laisse **de la place pour les images**, et on explique que tu n’as testé qu’une seule image. Voilà une version **propre, cohérente et prête à mettre sur GitHub** :

---

```markdown
# Object Detection – YOLOv8 & SSD MobileNet v2

**Type : Academic Project / Computer Vision Exploration**  

---

## 📘 Contexte et Motivation
J’ai entendu parler des modèles de vision par ordinateur et j’ai voulu **les découvrir concrètement**.  
Avant ce projet, je n’avais jamais utilisé YOLO ni SSD MobileNet, donc l’objectif était **d’apprendre à charger, tester et comparer des modèles simples**, et comprendre les concepts de base avant d’approfondir ces notions dans des projets plus complexes en entreprise.

---

## 🎯 Objectifs
- Comprendre et expérimenter les bases de la détection d’objets avec des modèles pré-entraînés.  
- Comparer deux architectures populaires :  
  - **YOLOv8** (Ultralytics) : rapide et léger  
  - **SSD MobileNet v2** : précis, mais plus lent  
- Développer une **interface simple** pour visualiser les détections et ajuster le seuil de confiance.  
- Documenter les résultats observés et noter les différences entre modèles.

---

## 🧰 Stack & Outils
- **Langage :** Python 3.10+  
- **Interface :** Streamlit  
- **Traitement d’image :** OpenCV, PIL  
- **Modèles :** YOLOv8 (Ultralytics), SSD MobileNet v2 (TensorFlow Hub)  
- **Gestion dépendances :** `requirements.txt`  
- **Script de lancement Windows :** `lancement_streamlit.bat`  

---

## ⚙️ Méthodologie
1. **Prétraitement de l’image** : conversion BGR/RGB selon le modèle.  
2. **Chargement du modèle choisi** (YOLOv8 ou SSD MobileNet v2).  
3. **Détection et filtrage** : seuil de confiance ajustable.  
4. **Visualisation** : dessin des boîtes englobantes et labels sur les images.  
5. **Interface interactive** : upload d’image, choix du modèle, ajustement du seuil.  
6. **Comparaison des résultats** : nombre d’objets détectés et observations qualitatives.

--- 

## 📊 Résultats Observés

| Modèle           | Objets détectés (approx.) | Temps relatif |
|-----------------|---------------------------|---------------|
| YOLOv8n         | Objets principaux         | Très rapide   |
| SSD MobileNet v2 | Objets principaux + petits | Plus lent    |

- Une seule image testée pour ce projet.  

- **Observations :**
  - YOLOv8 détecte rapidement la plupart des objets principaux, mais peut manquer certains plus petits.  
  - SSD MobileNet v2 est plus précis pour les petits objets ou objets proches les uns des autres, mais plus lent.  
  - Le seuil de confiance influence le nombre de détections : 0.5 est un bon compromis.  

💡 Cette expérience m’a permis de comprendre les pipelines de vision par ordinateur et de préparer mes compétences pour des projets industriels plus avancés.

---

## 📁 Contenu du projet
```

object-detection-yolo-ssd/
├── app.py                       # Application Streamlit
├── requirements.txt             # Packages nécessaires
├── lancement_streamlit.bat      # Script Windows
├── README.md                    # Ce fichier
└── images/                      # Ici vous pouvez ajouter vos screenshots / images test

````

---

## 🚀 Lancer l’application
1. Cloner ou télécharger le projet.  
2. Installer les dépendances :  
   ```bash
   pip install -r requirements.txt
````

3. Lancer l’application :

   ```bash
   streamlit run app.py
   ```

   L’application s’ouvrira dans le navigateur sur `http://localhost:8501`.
4. Sur Windows, vous pouvez aussi double-cliquer sur `lancement_streamlit.bat`.

---

## 🖼️ Notes / Exemples de résultats

* YOLOv8 : détection rapide des objets principaux, parfait pour prototypage rapide.
* SSD MobileNet v2 : détection plus fine, surtout pour des objets petits ou proches.
* **Images / screenshots** peuvent être ajoutés dans le dossier `images/` pour illustrer les résultats.

---

## 👩🏽‍💻 Auteur

Rosette-Michèle Otounga – Projet académique

```

---


