# 🏠 Prédiction de Prix Immobiliers avec Machine Learning

## 🌞 Pourquoi ce projet ?

Ce projet est né de mon envie d'explorer un problème concret : **comment estimer le prix d'un bien immobilier à partir de ses caractéristiques**.

Le marché immobilier est un domaine où les données jouent un rôle important. Des variables comme la surface, l'âge du logement ou la localisation influencent fortement les prix. Construire un modèle capable d'identifier ces relations est un excellent exercice pour comprendre **comment les algorithmes apprennent à partir des données**.

Au-delà de la performance du modèle, ce projet m'intéresse aussi pour une autre raison : réfléchir à **la manière dont les modèles prennent leurs décisions**, et aux biais potentiels qui peuvent apparaître dans les prédictions.

---

## 🎯 Objectifs du projet

Construire un pipeline de data science complet à partir du dataset **Kaggle House Prices** :

- exploration et compréhension des données
- nettoyage et préparation des données
- création de nouvelles variables utiles (feature engineering)
- entraînement et comparaison de plusieurs modèles de machine learning
- analyse des biais potentiels dans les prédictions
- déploiement d'une application interactive avec Streamlit

---

## 📸 Aperçu

| Prédiction de prix | Visualisations |
|:------------------:|:--------------:|
| ![Prédiction](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/House_ml_project_Prediction_page.png) | ![Visualisations](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/House_ml_project_Visualisation_page.png) |

| Exploration des données |
|:-----------------------:|
| ![Données](https://raw.githubusercontent.com/soley000/omr-portfolio/main/assets/images/House_ml_project_Data_page.png) |

---

## 📊 Dataset

**House Prices – Advanced Regression Techniques**
👉 https://www.kaggle.com/c/house-prices-advanced-regression-techniques

Ce dataset contient des informations détaillées sur des maisons résidentielles (Ames, Iowa) :
surface habitable, année de construction, qualité des matériaux, caractéristiques du quartier, etc.

> ⚠️ Les fichiers `train.csv` et `test.csv` ne sont pas inclus dans ce dépôt (licence Kaggle).
> Téléchargez-les depuis le lien ci-dessus et placez-les dans le dossier `data/`.

---

## ⚙️ Pipeline de Machine Learning

### 1️⃣ Exploration des données (EDA)
Analyse de la structure, des distributions, des valeurs manquantes et des corrélations.

### 2️⃣ Préparation des données — `src/preprocessing.py`
- Imputation des valeurs manquantes (médiane pour le numérique, `'None'` pour le catégoriel)
- Suppression des outliers via la méthode IQR
- Encodage one-hot des variables catégorielles

### 3️⃣ Feature Engineering — `src/feature_engineering.py`

Trois nouvelles variables sont créées :

| Variable | Calcul | Intérêt |
|---|---|---|
| `AgeLogement` | 2025 - YearBuilt | Exprime directement l'ancienneté |
| `SurfaceTotale` | GrLivArea + TotalBsmtSF | Taille utile totale de la maison |
| `NbSallesDeBain` | FullBath + 0.5 × HalfBath | Représentation pondérée des sanitaires |

Les colonnes d'origine devenues redondantes sont supprimées.

### 4️⃣ Modélisation — `src/modeling.py`

Trois modèles sont entraînés et comparés :

| Modèle | Description |
|---|---|
| Régression Linéaire | Modèle de référence, simple et interprétable |
| Random Forest | Ensemble d'arbres, robuste aux non-linéarités |
| Gradient Boosting | Boosting séquentiel, généralement le plus performant |

Métriques d'évaluation : **R²** et **MAE (Mean Absolute Error)**

Le meilleur modèle est automatiquement sélectionné et sauvegardé.

---

## ⚖️ Analyse des biais

Les modèles prédictifs peuvent être plus précis sur certaines zones que d'autres.

Une analyse des erreurs par **quartier (`Neighborhood`)** permet d'identifier des disparités systématiques dans les prédictions et de réfléchir à l'équité du modèle.

---

## 🖥️ Application Streamlit

L'application interactive permet de :
- **prédire** le prix d'une maison en saisissant ses caractéristiques
- **choisir le modèle** de prédiction (Random Forest, Gradient Boosting, Régression Linéaire)
- **explorer** les données avec des visualisations filtrables
- **télécharger** les données filtrées en CSV

---

## 🛠️ Technologies utilisées

| Catégorie | Outils |
|---|---|
| Langage | Python 3.11 |
| Manipulation des données | Pandas, NumPy |
| Machine Learning | Scikit-learn |
| Visualisation | Matplotlib, Seaborn, Plotly |
| Application | Streamlit |
| Sérialisation | Joblib |

---

## 📁 Structure du projet

```
house-price-ml-project/
│
├── data/                          # Données brutes (non versionnées)
│   ├── train.csv
│   └── test.csv
│
├── notebooks/
│   └── house_price_analysis.ipynb # Pipeline complet : EDA → modèles → biais
│
├── src/
│   ├── __init__.py
│   ├── preprocessing.py           # Nettoyage et encodage
│   ├── feature_engineering.py     # Création de nouvelles variables
│   └── modeling.py                # Entraînement et évaluation des modèles
│
├── models/                        # Modèles sauvegardés (non versionnés)
│   ├── best_model.pkl
│   ├── scaler.pkl
│   └── feature_columns.pkl
│
├── app_streamlit.py               # Application interactive
├── requirements.txt
└── README.md
```

---

## 🚀 Lancer le projet

**1. Installer les dépendances**
```bash
pip install -r requirements.txt
```

**2. Télécharger les données**

Téléchargez `train.csv` et `test.csv` depuis [Kaggle](https://www.kaggle.com/c/house-prices-advanced-regression-techniques) et placez-les dans `data/`.

**3. Exécuter le notebook**

Ouvrez `notebooks/house_price_analysis.ipynb` et exécutez toutes les cellules (Kernel → Restart & Run All).
Cela génère les fichiers dans `models/`.

**4. Lancer l'application**
```bash
streamlit run app_streamlit.py
```

---

## 👩🏽‍💻 Auteure

**Rosette-Michèle Otounga**
Apprentie Big Data Engineering & Applied AI/ML

[GitHub](https://github.com/soley000) · [LinkedIn](https://linkedin.com/in/rosette-michele) · [Portfolio](https://github.com/soley000/omr-portfolio)
