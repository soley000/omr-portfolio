# 🔬 Vision Models Evaluation – Cosmos Reason1 & Reason2

## 📌 Contexte et objectif

Ce projet a pour objectif d’évaluer plusieurs **modèles vision-language** appliqués à l’analyse de scènes de conduite.

L’évaluation est réalisée sur un **mini-dataset de scénarios urbains**, avec une méthodologie inspirée de pratiques standards d’évaluation de modèles IA.

### Objectifs principaux :

* Tester la capacité des modèles à décrire correctement des scènes de conduite.
* Vérifier la détection d’objets critiques (piétons, cyclistes, véhicules).
* Évaluer la cohérence spatiale et temporelle des prédictions.
* Mesurer les performances techniques : temps d’inférence, stabilité.
* Identifier l’effort nécessaire pour l’intégration et le prétraitement.

---

## 🧩 Présentation des modèles

| Modèle         | Description                                                       | Points forts                                       | Limitations                                                                        |
| -------------- | ----------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Cosmos Reason1 | Vision-Language 7B, analyse images/vidéos, description structurée | Bonne compréhension statique, peu d’hallucinations | Faible temporalité, temps d’inférence élevé (~72s), sensible à la durée des vidéos |
| Cosmos Reason2 | Vision-Language 2B, code + poids distribués via HuggingFace       | Meilleure précision, gestion des modèles lourds    | Poids lourds (~5 Go), setup Git LFS et HuggingFace nécessaire                      |

---

## 🛠 Environnement technique

* **OS** : Ubuntu 22.04 / VM NVIDIA Cloud
* **GPU** : NVIDIA Ampere (A100 recommandé)
* **CUDA** : 11.8
* **Python** : 3.10.13
* **Conda** : 23.11.0

💡 GPU dédié fortement recommandé. Les vidéos courtes (~quelques secondes) limitent le raisonnement temporel.

---

## 📂 Structure des fichiers

```
Vision_Models_Evaluation/
├── COSMOS_Reason1/
│   ├── scripts/inference.py
│   ├── prompts/driving.yaml
│   └── ...
├── COSMOS_Reason2/
│   ├── code/               # Repo principal
│   └── models/             # Poids HuggingFace
├── data/raw/scenarios_demo/
│   ├── scenario_01/segment.webm
│   └── ... jusqu’au scenario_08
└── outputs/
    ├── spike_cosmos_reason1/
    └── spike_cosmos_reason2/
```

### Artefacts générés (exemple Reason1) :

```
outputs/spike_cosmos_reason1/scenario_01/
├── analysis.json
├── metrics_time.json
├── raw_stdout.txt
└── artifacts/video_0/0.png, 1.png, ...
```

---

## ⚙️ Exécution des modèles

### Cosmos Reason1 – un scénario

```bash
uv run scripts/inference.py \
  --prompt prompts/driving.yaml \
  --question "Analyze this driving scene, identify surrounding objects, road context, and potential safety risks." \
  --videos ../data/raw/scenarios_demo/scenario_01/segment.webm \
  -o outputs/spike_cosmos_reason1/scenario_01/analysis.json
```

### Cosmos Reason1 – batch 8 scénarios

```bash
for i in {01..08}; do
  mkdir -p outputs/spike_cosmos_reason1/scenario_$i/artifacts
  /usr/bin/time -f '{"inference_time_sec": %e}' \
  uv run scripts/inference.py \
    --prompt prompts/driving.yaml \
    --question "Analyze this driving scene, identify surrounding objects, road context, and potential safety risks." \
    --videos ../data/raw/scenarios_demo/scenario_$i/segment.webm \
    -o outputs/spike_cosmos_reason1/scenario_$i/analysis.json \
    1> outputs/spike_cosmos_reason1/scenario_$i/raw_stdout.txt \
    2> outputs/spike_cosmos_reason1/scenario_$i/metrics_time.json
done
```

---

## 🔹 Pipeline / Prétraitement (Spike)

| Étape                   | Réalisé par        | Effort         | Commentaires          |
| ----------------------- | ------------------ | -------------- | --------------------- |
| Clonage repo            | Utilisateur        | Faible         | git clone             |
| Init env                | Utilisateur        | Moyen          | Conda + uv            |
| Téléchargement poids    | Automatique        | Élevé (~15 Go) | Safetensors           |
| Extraction frames PNG   | Automatique        | Opaque         | qwen-vl-utils         |
| Parsing output          | Utilisateur        | Moyen          | JSON final            |
| Sauvegarde JSON et logs | Script + post-proc | Moyen          | Organisation fichiers |

💡 Ici, il n’y a pas de pipeline que je construis : je suis strictement la **trame NVIDIA**, c’est un **spike d’évaluation**.

---

## 📊 Analyse qualitative (exemple Cosmos Reason1)

Axes d’évaluation :

* **détection d'Objets** : piétons, cyclistes, véhicules
* **cohérence spatiale** : cohérence spatiale
* **cohérence temporelle** : dynamique de la scène
* **identification des risques** : pertinence par rapport au GT
* **Fidélité de description** : absence d’hallucinations
* **Focus** : attention aux éléments critiques

| Scénario | Temps Inf. | Objets                | Risque              | Notes principales        | Obj. | Spatial | Temporel | Risque | Fidélité | Focus | Alignement GT |
| -------- | ---------- | --------------------- | ------------------- | ------------------------ | ---- | ------- | -------- | ------ | -------- | ----- | ------------- |
| 01       | 71s        | passage piéton, route | faible              | Risque sous-estimé       | ✅    | 🟡      | 🟡       | 🟡     | ✅        | 🟡    | 🟡            |
| 02       | 74s        | cycliste, véhicules   | vigilance générique | Trajectoire non comprise | ✅    | 🟡      | ❌        | 🟡     | ✅        | 🟡    | 🟡            |

✅ : correct, 🟡 : partiel, ❌ : incorrect

---

## ⚠️ Limites & Next Steps

* Temps d’inférence élevé (~72s), sensible aux vidéos longues.
* Les spikes servent à préparer un **benchmark officiel futur** pour les World Models.
* Vérification qualitative des sorties JSON avec GT recommandée.
* Documenter les artefacts pour faciliter l’analyse globale.

---

## 📌 Ce que j’ai appris

* Setup GPU / HuggingFace auth en environnement entreprise.
* Analyse qualitative et mesure de performance des modèles Cosmos.

---

