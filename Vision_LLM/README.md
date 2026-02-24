# Vision + LLM (Évaluation des hallucinations)

## 📌 Contexte
Projet IA appliquée sur un modèle interne de **coaching de conduite** développé au sein de l'équipe Innovation de Ampere (Renault).
Le coaching analyse des vidéos de scènes de conduite et génère des descriptions et des conseils (ex : “ralentir car un piéton traverse”) et peut **halluciner des objets** (mentionner des objets qui n’existent pas).

Mon rôle : construire une **pipeline d’évaluation automatisée** pour détecter ces hallucinations et mesurer la fiabilité du coaching.

---

## 🧩 Problématique
- Vérifier automatiquement si les objets mentionnés par le coaching existent réellement dans les frames vidéo.
- Mesurer la fiabilité globale du modèle avec des métriques : précision, rappel, F1-score.
- Pipeline **robuste, reproductible, scalable**, mais présenté ici en version **no-code / portfolio**.

---

## ⚙️ Pipeline / Architecture
```mermaid
graph LR
A[JSON annotations + frames vidéo] --> B[LLMExtractor]
B --> C[RAMBackend]
C --> D[AutoNormalizer]
D --> E[HallucinationChecker]
E --> F[CSV résumé + métriques]
````

### 🔹 Description des composants

1. **LLMExtractor** : extrait objets mentionnés dans le texte de coaching.
2. **RAMBackend** : détecte objets réels dans les frames vidéo (ex. Recognize Anything Model).
3. **AutoNormalizer** : harmonise FR/EN et regroupe synonymes.
4. **HallucinationChecker** : compare objets coaching vs RAM → détecte hallucinations.
5. **CSV & Metrics** : génère rapport par vidéo, calcule précision, rappel, F1, matrice de confusion.

---

## 🛠 Méthodologie

* Création d’un mini dataset simulé (frames + JSON) pour illustrer le pipeline.
* Normalisation des objets FR/EN pour comparaison.
* Comparaison entre coaching et détection visuelle RAM.
* Évaluation automatisée : CSV par vidéo + métriques globales.

---

## 📊 Mini dataset simulé (ex pas dataset réel)

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

**frames/** : 2-3 images fictives par vidéo, ex. `video_001/frame_001.jpg`, `video_002/frame_001.jpg`.

---

## 🏆 Résultats / Livrables

* Pipeline fonctionnelle pour détection automatique d’hallucinations.
* CSV résumé (exemple) :

| video_id  | hallucination_pred | missing_object |
| --------- | ------------------ | -------------- |
| video_001 | False              |                |
| video_002 | True               | crosswalk      |

* Métriques simulées :

  * Accuracy : 70%
  * Precision : 15%
  * Recall : 27%
  * F1-score : 19%

💡 Interprétation : le pipeline détecte correctement les absences d’hallucination mais nécessite encore optimisation sur les hallucinations réelles.

---

## ⚠️ Limites & Perspectives

* Mini dataset simulé → montre la méthodologie mais pas la vraie performance.
* Normalisation FR/EN peut être améliorée.
* Nombre de frames (k=60) → à tester pour optimiser performance.
* Pipeline intégrable sur serveur/cloud pour industrialisation.

---

## 💡 Recommandations / Next Steps

* Repenser LLMExtractor et AutoNormalizer pour plus de robustesse.
* Pipeline unifiée : entrée = dossier vidéo + JSON, sortie = CSV + métriques + matrice de confusion.
* Tester différents paramètres pour maximiser précision et rappel (>80%).

---

## 📁 Organisation des fichiers

```
Vision_LLM/
├─ README.md
├─ mini_dataset/
│   ├─ frames/
│   └─ annotations.json

```
