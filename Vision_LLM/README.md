# Vision + LLM (Évaluation hallucinations)

## 📌 Contexte
Projet IA appliquée pour évaluer les hallucinations d’un modèle multimodal Vision + LLM.
Objectif : fiabiliser les réponses générées et analyser les limites du modèle.

## 🧩 Problématique
Les LLM multimodaux peuvent produire des hallucinations ou erreurs factuelles.
Détecter et mesurer ces hallucinations est essentiel pour l’usage en production.

## ⚙️ Pipeline / Architecture
```mermaid
graph LR
A[Images d'entrée] --> B[Prétraitement]
B --> C[Modèle Recognize Anything + LLM]
C --> D[Sortie texte annoté]
D --> E[Analyse hallucinations]
````
🛠 Méthodologie

Prétraitement des images (normalisation, redimensionnement)

Génération de légendes / réponses avec LLM

Évaluation des hallucinations avec métriques automatisées (precision, recall)

Comparaison entre modèles et réglage hyperparamètres

📊 Dataset

Mini dataset simulé : 5 images fictives + descriptions CSV

Colonnes : image_id, description_attendue

🏆 Résultats / Livrables

Tableau de métriques par image et modèle

Graphiques : hallucinations les plus fréquentes

Impact : meilleure compréhension des limites du modèle

⚠️ Limites / Perspectives

Extension à d’autres types d’images

Automatisation de la correction des hallucinations

💡 Recommandations / Next Steps

Intégrer module de validation humaine
