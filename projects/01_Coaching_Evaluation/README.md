# 👁️ Vision & LLM Evaluation Framework for Driving Scenarios

## 📌 Contexte
Projet IA appliquée sur un modèle interne de **coaching de conduite** développé au sein de l'équipe Innovation de Ampere (Renault).
Le coaching analyse des vidéos de scènes de conduite et génère des descriptions et des conseils (ex : “ralentir car un piéton traverse”).
Problème : le modèle peut **halluciner des objets** (mentionner des objets qui n’existent pas).

Mon rôle : construire une **pipeline d’évaluation automatisée** pour évaluer automatiquement les sorties du coaching et détecter les hallucinations.

---

## 🧩 Problématique
- Vérifier automatiquement si les objets mentionnés par le coaching existent réellement dans les frames vidéo.
- Mesurer la fiabilité globale du modèle avec des métriques : précision, rappel, F1-score.
- Pipeline **robuste, reproductible, scalable**, mais présenté ici en version **no-code / portfolio**.

---

## ⚙️ Pipeline / Architecture
```mermaid
flowchart LR
A[JSON coaching output] --> B[LLMExtractor]
B --> C[AutoNormalizer]
D[Frames vidéo] --> E[RAMBackend]
C --> F[HallucinationChecker]
E --> F
F --> G[CSV & Matrices de confusion 📊]
````

### 🔹 Description des composants

1. **LLMExtractor** : extrait objets mentionnés dans le texte de coaching.
2. **RAMBackend** : détecte objets réels dans les frames vidéo (ex. Recognize Anything Model).
3. **AutoNormalizer** : harmonise FR/EN et regroupe synonymes.
4. **HallucinationChecker** : compare objets coaching vs RAM → détecte hallucinations.
5. **CSV & Metrics** : génère rapport par vidéo, calcule précision, rappel, F1, matrice de confusion.

---

## 🛠 Méthodologie

* Extraction objets via LLM
* Détection objets via RAM
* Normalisation des objets FR/EN pour comparaison.
* Comparaison entre coaching et détection visuelle RAM.
* Évaluation automatisée : CSV par vidéo + métriques globales.

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

* Pipeline fonctionnelle pour détection automatique d’hallucinations.
* CSV résumé (exemple) :

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
## Confidentialité

* Données sensibles : non exposées
* Code interne : non partagé
* Résultats et architecture montrés pour démonstration uniquement

## Ce que j’ai appris

* Pipeline d’évaluation robuste
* Méthodologie métrique complète
