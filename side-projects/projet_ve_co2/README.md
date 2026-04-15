# 🌱 Réduction de CO₂ par l'adoption des véhicules électriques (VE) — Application IA personnalisée

Ce projet a pour but de **quantifier et prédire la réduction des émissions de CO₂** générée par l'adoption progressive des véhicules électriques (VE) en France.
Il s'appuie sur des **données publiques** et l'intégration d'un **modèle d'intelligence artificielle Prophet** afin de personnaliser les résultats selon les habitudes de l'utilisateur.

> 📌 Projet personnel imaginé et conçu par Rosette-Michèle Otounga.
> Au fil de mon apprentissage en Big Data et en IA appliquée, j'ai voulu construire quelque chose de concret qui me ressemble — un projet qui croise deux sujets qui me tiennent à cœur : l'intelligence artificielle et l'écologie. L'idée était simple : montrer que les données et les modèles d'IA peuvent rendre visible et mesurable quelque chose d'aussi important que l'impact de nos choix de mobilité sur le climat. Montrer qu'on peut le faire, et que ça a du sens.

---

## 🎯 Objectifs

- Proposer une **application interactive Streamlit** intégrant une logique métier environnementale.
- **Personnaliser** les estimations CO₂ en fonction du type de véhicule, de la consommation et du kilométrage annuel de l'utilisateur.
- **Projeter les émissions futures** à l'échelle nationale grâce à **l'IA (Prophet)**.
- Simuler les **gains individuels et collectifs** en CO₂ selon différents scénarios d'adoption.

---

## 📸 Aperçu

| Bilan CO₂ individuel | Prédictions Prophet |
|:--------------------:|:-------------------:|
| ![Bilan](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/ve_co2_bilan.png) | ![Prophet](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/ve_co2_prophet.png) |

| Impact collectif & bilan cumulé |
|:-------------------------------:|
| ![Impact](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/ve_co2_impact.png) |

---

## 🧠 Choix du modèle d'IA — Pourquoi Prophet ?

Le choix du modèle n'a pas été immédiat. Deux modèles ont été évalués et comparés avant de retenir Prophet.

### Modèles comparés

| Critère | Prophet | SVR (scikit-learn) |
|---|---|---|
| Type | Série temporelle statistique | Régression à vecteurs de support |
| Données nécessaires | **Fonctionne bien avec peu de points** | Surapprentissage sur peu de points |
| Notre dataset | 14 points annuels ✅ | 14 points → mémorise, ne généralise pas ❌ |
| Courbe en S (adoption technologique) | Modélisée nativement (`growth='logistic'`) ✅ | Non native — extrapolation non contrôlée ❌ |
| Valeurs hors [0%, 100%] possibles | Non — borné par `floor=0, cap=0.40` ✅ | Oui — prédictions illogiques observées ❌ |
| Intervalles de confiance | Natifs ✅ | Non disponibles ❌ |
| Stabilité des prédictions | Stable et reproductible ✅ | Sensible aux hyperparamètres ❌ |
| Bornes physiques intégrées | Native (`floor`, `cap`) ✅ | Non native ❌ |

### Ce qu'on a observé concrètement

Le SVR a été testé en premier. Avec seulement 14 points d'entraînement, il produit une MAE très basse sur les données connues — signe qu'il les **mémorise** plutôt qu'il ne les apprend. En dehors de cette plage, ses prédictions deviennent **non contrôlées** : valeurs négatives ou supérieures à 100% possibles, ce qui est physiquement impossible pour une part de marché.

Prophet, configuré avec une **croissance logistique** (courbe en S), a produit des prédictions cohérentes avec la dynamique réelle du marché : décollage progressif jusqu'en 2020, puis accélération marquée, avec un plafonnement réaliste vers 2033–2035.

### Justification technique

```
Adoption d'une technologie = courbe en S
    → faible au départ
    → décollage rapide une fois le seuil de masse critique atteint
    → plafonnement quand le marché est saturé

Prophet growth='logistic' modélise exactement cette dynamique.
SVR sur 14 points = surapprentissage, extrapolation non bornée.
```

La comparaison est documentée et visualisée dans le **notebook 02**, section 5.

---

## 🖥️ Fonctionnalités de l'application

**L'utilisateur renseigne :**
- Le **type de carburant** utilisé actuellement
- Sa **consommation moyenne** (L/100 km)
- Le **nombre de kilomètres** parcourus par an
- L'**année de passage** au véhicule électrique
- Le **scénario d'adoption nationale** — conservateur (×0.7), réaliste (prédiction Prophet), ambitieux (×1.4) — tous bornés à 50% maximum

**L'application calcule et affiche :**
- Les **émissions annuelles actuelles** en CO₂
- Les émissions estimées avec un **VE** (usage + fabrication inclus)
- Le **gain annuel** en kg et l'équivalent en arbres plantés 🌳
- Le **seuil de rentabilité environnementale** (en km et en années)
- **4 sections interactives :**
  - Bilan CO₂ individuel
  - Projections nationales Prophet (part de marché + émissions collectives)
  - Impact collectif si les nouvelles immatriculations suivaient votre profil
  - Votre bilan cumulé depuis votre passage au VE

---

## 📁 Structure du projet

```
projet_ve_co2/
│
├── data/
│   ├── emissions_vehicules_ademe.csv         ← ADEME (sep=";", ISO-8859-1)
│   ├── part_marche_ve.csv                    ← data.gouv.fr
│   ├── intensite_carbone.csv                 ← Our World in Data
│   ├── points_de_charge.csv                  ← data.gouv.fr (sep=";")
│   └── prepared/                             ← générés par le notebook 01
│       ├── df_clean.csv
│       ├── df_intensite_fr.csv
│       ├── df_part_annee.csv                 ← input Prophet
│       ├── df_points_yearly.csv
│       ├── df_fusion.csv
│       └── df_points_part.csv
│
├── notebooks/
│   ├── 01_exploration_donnees.ipynb          ← EDA complète + préparation données
│   └── 02_modelisation_prediction_co2.ipynb  ← Comparaison SVR vs Prophet + modélisation
│
├── streamlit_app/
│   ├── run_app.py                            ← Application Streamlit
│   └── forecast_prophet.csv                 ← généré par le notebook 02
│
├── requirements.txt
└── README.md
```

---

## 📦 Installation

```bash
pip install -r requirements.txt
```

---

## ▶️ Ordre d'exécution

```bash
# 1. Exploration et préparation des données
jupyter notebook notebooks/01_exploration_donnees.ipynb

# 2. Comparaison des modèles + génération du forecast
jupyter notebook notebooks/02_modelisation_prediction_co2.ipynb

# 3. Lancement de l'application
cd streamlit_app
streamlit run run_app.py
```

---

## 🔍 Sources de données

### Datasets utilisés — pertinence et limites

**`emissions_vehicules_ademe.csv`** — ADEME
Catalogue des émissions CO₂ homologuées par modèle de véhicule (g/km).
✅ Utilisé pour extraire les valeurs de référence CO₂ VE (49.33 g/km) et thermique, et construire la colonne `motorisation`.
⚠️ Contient très peu de VE (9 modèles) car les VE n'ont pas d'émissions à l'échappement — leur CO₂ est mesuré sur l'ensemble du cycle de vie, pas à la sortie du pot d'échappement. Lorsque la moyenne calculée sur ces 9 modèles est disponible, elle est utilisée directement (49.33 g/km). Si elle ne l'était pas, on utiliserait la valeur officielle publiée par l'ADEME en 2023 — c'est ce qu'on appelle une valeur de secours (fallback).

**`part_marche_ve.csv`** — data.gouv.fr
Part des véhicules électriques dans les **immatriculations annuelles** (voitures neuves), par commune, catégorie et année.
✅ C'est la variable cible de Prophet — elle mesure la dynamique de transition, pas le parc total en circulation.
⚠️ Important : une part de 23.7% en 2023 signifie que 23.7% des **nouvelles** voitures vendues cette année-là étaient électriques, et non 23.7% des voitures sur la route.

**`intensite_carbone.csv`** — Our World in Data
Intensité carbone de l'électricité en gCO₂/kWh par pays et par année.
✅ Permet de contextualiser l'empreinte réelle d'un VE selon le mix électrique du pays. En France, ce chiffre baisse grâce au nucléaire (44 gCO₂/kWh en 2024).
ℹ️ Utilisé dans l'analyse exploratoire (corrélation avec l'adoption VE) mais pas directement dans l'appli — la valeur CO₂ VE usage de 49.33 g/km intègre déjà le mix français.

**`points_de_charge.csv`** — data.gouv.fr
Nombre de points de recharge publics par trimestre en France.
✅ Indicateur corrélatoire de l'infrastructure VE — confirme que l'adoption et le déploiement progressent ensemble.
ℹ️ Utilisé en analyse exploratoire uniquement, pas dans la modélisation Prophet.

---

## 🚀 Déploiement

- En **local** via Streamlit comme démontré ci-dessus.
- Ou déployé sur **Streamlit Cloud** ([streamlit.io/cloud](https://streamlit.io/cloud)) avec un simple `git push`.

---

## ✨ Conclusion

Ce projet démontre **comment l'IA peut rendre compréhensible et mesurable l'impact écologique individuel**, et comment un simple changement de véhicule pourrait réduire significativement les émissions de CO₂ en France. Le choix rigoureux du modèle — justifié par une comparaison concrète avec le SVR — montre qu'en data science, le bon modèle n'est pas forcément le plus complexe, mais celui qui correspond à la réalité des données disponibles.

---

## 🧑🏾‍💻 Auteure

**Rosette-Michèle Otounga**
Apprentie Big Data Engineering & Applied AI/ML

[GitHub](https://github.com/soley000) · [LinkedIn](https://linkedin.com/in/rosette-michele) · [Portfolio](https://github.com/soley000/omr-portfolio)
