# 👁️ Vision & LLM Evaluation Framework for Driving Scenarios

## 📌 Contexte
Projet IA appliquée sur un modèle interne de **coaching de conduite** un contexte industriel d’innovation.

Ce système analyse des vidéos de scènes de conduite et génère automatiquement des descriptions et des conseils de conduite (par exemple : « *ralentir car un piéton traverse* »).

Un problème identifié est la possibilité que le modèle **hallucine certains objets**, c’est-à-dire qu’il mentionne des éléments qui ne sont pas réellement présents dans la scène.

Mon rôle a été de **concevoir une pipeline d’évaluation automatisée** permettant d’analyser les sorties du système et de détecter ces hallucinations.
---

## 🧩 Problématique

- Vérifier automatiquement si les objets mentionnés par le coaching existent réellement dans les frames vidéo.
- Mesurer la fiabilité globale du modèle avec des métriques : précision, rappel, F1-score.
Pour cela, la pipeline permet de :

* extraire les objets mentionnés dans les descriptions générées

* détecter les objets réellement présents dans les images

* comparer les deux sources d’information

* calculer des métriques d’évaluation (precision, recall, F1-score)

L’objectif est de disposer d’une pipeline robuste, reproductible et scalable, présentée ici sous forme documentée sans code interne.
---

## ⚙️ Pipeline / Architecture

### 🔹 Composants principaux

1. **LLMExtractor** : extrait objets mentionnés dans le texte de coaching.
2. **RAMBackend** : détecte objets réels dans les frames vidéo (ex. Recognize Anything Model).
3. **AutoNormalizer** : harmonise FR/EN et regroupe synonymes.
4. **HallucinationChecker** : compare objets coaching vs RAM → détecte hallucinations.
5. **Metrics** : génère rapport par vidéo, calcule précision, rappel, F1, matrice de confusion.

---

## 🛠 Méthodologie

1. Extraction des objets mentionnés dans les descriptions générées

2. Détection d’objets présents dans les frames vidéo

3. Normalisation linguistique pour faciliter la comparaison

4. Comparaison entre description générée et détection visuelle

5. Calcul automatique des métriques d’évaluation

La pipeline produit :

* un rapport CSV par vidéo

* des métriques globales d’évaluation
---

## 📊 exemple datasets

**annotations.json** :

```json
{
  "video_001.webm": {
    "context": "Un cycliste roule sur la route, une voiture arrive derrière lui.",
    "hallucination": "no"
  },
  "video_002.webm": {
    "context": "Deux piétons traversent au passage piéton près d'un bus.",
    "hallucination": "yes"
  }
}
```

**frames/** : 2-3 images par vidéo, ex. `video_001/frame_001.jpg`, `video_002/frame_001.jpg`.

---

## 🏆 Résultats / Livrables

La pipeline permet :

* la détection automatisée d’hallucinations potentielles

* la génération de rapports d’évaluation

* le calcul de métriques globales

Exemple simplifié de sortie :

| Vidéo | Hallucination prédite | Objets manquants | GT    | Accord |
| ----- | --------------------- | ---------------- | ----- | ------ |
| 1_001 | False                 | -                | False | True   |
| 1_005 | True                  | traffic_light    | True  | True   |


* Métriques :

  * Accuracy : 70%
  * Precision : 15%
  * Recall : 27%
  * F1-score : 19%

💡 Interprétation : le pipeline détecte correctement les absences d’hallucination mais nécessite encore optimisation sur les hallucinations réelles.

---

## ⚠️ Limites & Perspectives

* Normalisation FR/EN peut être améliorée.
* Nombre frames par vidéo (k=60) → impact sur metrics
* Données GT limitées (86/155 vidéos)

---

## 💡 Recommandations / Next Steps

* Repenser LLMExtractor et AutoNormalizer pour plus de robustesse.
* Pipeline unifiée : entrée = dossier vidéo + JSON, sortie = CSV + métriques + matrice de confusion.
* Tester différents paramètres pour maximiser précision et rappel (>80%).

---

## Ce que j’ai appris

* Conception de pipelines d’évaluation de modèles IA

* Définition de métriques d’analyse pertinentes

* Comparaison automatique entre sources de données textuelles et visuelles
