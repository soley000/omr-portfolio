import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import joblib

sns.set_style("whitegrid")

# ===============================
# Configuration page
# ===============================
st.set_page_config(page_title="🏠 Prédiction Prix Immobiliers", layout="wide")
st.title("🏠 Prédiction et Exploration du Prix des Maisons")
st.markdown("🌞 Analysez, explorez et prédisez le prix d'un bien immobilier")

# ===============================
# Chargement données et modèles
# ===============================
@st.cache_data
def load_data():
    return pd.read_csv("data/train.csv")

@st.cache_resource
def load_artifacts():
    scaler   = joblib.load("models/scaler.pkl")
    columns  = joblib.load("models/feature_columns.pkl")
    models   = {
        "🌲 Random Forest":     joblib.load("models/random_forest_model.pkl"),
    }
    # Charger les autres modèles s'ils existent
    import os
    if os.path.exists("models/gradient_boosting_model.pkl"):
        models["📈 Gradient Boosting"] = joblib.load("models/gradient_boosting_model.pkl")
    if os.path.exists("models/linear_regression_model.pkl"):
        models["📐 Régression Linéaire"] = joblib.load("models/linear_regression_model.pkl")
    return scaler, columns, models

try:
    train_df = load_data()
except FileNotFoundError:
    st.error("❌ Fichier 'data/train.csv' introuvable.")
    st.stop()

try:
    scaler, feature_columns, available_models = load_artifacts()
except FileNotFoundError:
    st.error("❌ Modèles introuvables dans 'models/'. Lancez d'abord le notebook.")
    st.stop()

# ===============================
# Feature engineering (identique à src/feature_engineering.py)
# ===============================
def create_features(df):
    df = df.copy()
    df["AgeLogement"]    = 2025 - df["YearBuilt"]
    df["SurfaceTotale"]  = df["GrLivArea"] + df["TotalBsmtSF"].fillna(0)
    df["NbSallesDeBain"] = df["FullBath"] + 0.5 * df["HalfBath"].fillna(0)
    df.drop(["YearBuilt", "GrLivArea", "TotalBsmtSF"], axis=1, inplace=True)
    return df

# ===============================
# Sidebar : Inputs utilisateur
# ===============================
st.sidebar.header("🏡 Caractéristiques de la maison")

GrLivArea   = st.sidebar.slider("Surface habitable (pi²)",  300,  5000, 1500, 50)
TotalBsmtSF = st.sidebar.slider("Surface sous-sol (pi²)",     0,  3000,  800, 50)
YearBuilt   = st.sidebar.slider("Année de construction",   1870,  2024, 1990,  1)
FullBath    = st.sidebar.slider("Salles de bain complètes",   0,     4,    2,  1)
HalfBath    = st.sidebar.slider("Demi-salles de bain",        0,     3,    0,  1)
OverallQual = st.sidebar.slider("Qualité générale (1–10)",    1,    10,    5,  1)
OverallCond = st.sidebar.slider("Condition générale (1–10)",  1,    10,    5,  1)
GarageCars  = st.sidebar.slider("Capacité garage (voitures)", 0,     4,    2,  1)

st.sidebar.markdown("---")
st.sidebar.header("🤖 Choix du modèle")
selected_model_name = st.sidebar.selectbox(
    "Modèle de prédiction",
    options=list(available_models.keys()),
    help="Random Forest et Gradient Boosting donnent généralement les meilleurs résultats."
)
selected_model = available_models[selected_model_name]

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtres visuels")
price_min_val = int(train_df['SalePrice'].min())
price_max_val = int(train_df['SalePrice'].max())
min_price, max_price = st.sidebar.slider(
    "Fourchette de prix ($)",
    price_min_val, price_max_val,
    (price_min_val, price_max_val),
    step=5000
)

# Données filtrées — partagées entre onglets
filtered = train_df[
    (train_df['SalePrice'] >= min_price) &
    (train_df['SalePrice'] <= max_price)
].copy()

# ===============================
# Onglets
# ===============================
tab1, tab2, tab3 = st.tabs(["💰 Prédiction", "📊 Visualisations", "📋 Données filtrées"])

# ───────────────────────────────
# ONGLET 1 – Prédiction
# ───────────────────────────────
with tab1:
    st.header(f"💰 Estimation du prix — {selected_model_name}")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📋 Récapitulatif")
        age_logement   = 2025 - YearBuilt
        surface_totale = GrLivArea + TotalBsmtSF
        nb_sdb         = FullBath + 0.5 * HalfBath

        summary = pd.DataFrame({
            "Caractéristique": [
                "Surface habitable", "Surface sous-sol", "Année de construction",
                "Salles de bain complètes", "Demi-salles de bain",
                "Qualité générale", "Condition générale", "Capacité garage",
                "── Variables dérivées ──",
                "Âge du logement", "Surface totale", "Salles de bain (pondéré)"
            ],
            "Valeur": [
                f"{GrLivArea} pi²", f"{TotalBsmtSF} pi²", str(YearBuilt),
                str(FullBath), str(HalfBath),
                f"{OverallQual}/10", f"{OverallCond}/10", f"{GarageCars} voiture(s)",
                "",
                f"{age_logement} ans", f"{surface_totale} pi²", str(nb_sdb)
            ]
        })
        st.table(summary)

    with col_right:
        st.subheader("🔮 Résultat")
        if st.button("💰 Prédire le prix", type="primary", use_container_width=True):
            try:
                # Construire la ligne de base avec les médianes/modes du train set
                base_row = {}
                for col in train_df.columns:
                    if col == 'SalePrice':
                        continue
                    if train_df[col].dtype == object:
                        base_row[col] = train_df[col].mode()[0]
                    else:
                        base_row[col] = train_df[col].median()

                # Injecter les valeurs saisies
                base_row.update({
                    'GrLivArea':   GrLivArea,
                    'TotalBsmtSF': TotalBsmtSF,
                    'YearBuilt':   YearBuilt,
                    'FullBath':    FullBath,
                    'HalfBath':    HalfBath,
                    'OverallQual': OverallQual,
                    'OverallCond': OverallCond,
                    'GarageCars':  GarageCars,
                })

                X_user = pd.DataFrame([base_row])

                # Feature engineering
                X_user = create_features(X_user)

                # Encodage one-hot
                X_user = pd.get_dummies(X_user, drop_first=True)

                # Aligner avec les colonnes d'entraînement
                X_user = X_user.reindex(columns=feature_columns, fill_value=0)

                # Scaling
                X_user_sc = scaler.transform(X_user)

                # Prédiction
                prediction = selected_model.predict(X_user_sc)[0]

                st.success(f"### 💵 Prix estimé : **{prediction:,.0f} $**")
                st.caption(f"Modèle utilisé : {selected_model_name}")
                st.balloons()

                # Jauge de positionnement dans le dataset
                p_min = train_df['SalePrice'].min()
                p_max = train_df['SalePrice'].max()
                pct   = (prediction - p_min) / (p_max - p_min)
                st.progress(
                    min(float(pct), 1.0),
                    text=f"Positionnement dans le dataset : {pct*100:.0f}ème centile"
                )

                # Comparaison rapide avec la moyenne du dataset
                mean_price = train_df['SalePrice'].mean()
                delta = prediction - mean_price
                st.metric(
                    label="Par rapport au prix moyen du dataset",
                    value=f"{prediction:,.0f} $",
                    delta=f"{delta:+,.0f} $"
                )

            except Exception as e:
                st.error(f"Erreur lors de la prédiction : {e}")
                st.info("Vérifiez que le notebook a bien été exécuté entièrement.")

# ───────────────────────────────
# ONGLET 2 – Visualisations
# ───────────────────────────────
with tab2:
    import plotly.express as px

    st.header("📊 Visualisations")
    st.caption(f"**{len(filtered):,} maisons** · filtre : {min_price:,} $ → {max_price:,} $")

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💵 Prix moyen",  f"{filtered['SalePrice'].mean():,.0f} $")
    k2.metric("📉 Prix min",    f"{filtered['SalePrice'].min():,.0f} $")
    k3.metric("📈 Prix max",    f"{filtered['SalePrice'].max():,.0f} $")
    k4.metric("🏠 Nb maisons",  f"{len(filtered):,}")
    st.markdown("---")

    # ── Ligne 1 : Distribution + Boxplot ──
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Distribution des prix")
        fig = px.histogram(
            filtered, x='SalePrice', nbins=50,
            color_discrete_sequence=['steelblue'],
            labels={'SalePrice': 'Prix ($)', 'count': 'Nb maisons'},
            height=350
        )
        fig.update_layout(margin=dict(t=20, b=20), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Prix par quartier")
        if 'Neighborhood' in filtered.columns:
            order = (filtered.groupby('Neighborhood')['SalePrice']
                     .median().sort_values().index.tolist())
            fig = px.box(
                filtered, x='Neighborhood', y='SalePrice',
                category_orders={'Neighborhood': order},
                color='Neighborhood',
                labels={'SalePrice': 'Prix ($)', 'Neighborhood': ''},
                height=350
            )
            fig.update_layout(margin=dict(t=20, b=20), showlegend=False,
                               xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Ligne 2 : 4 scatter plots en grille 2x2 ──
    st.subheader("Relations features → Prix")
    scatter_features = [
        ('GrLivArea',   'Surface habitable (pi²)'),
        ('OverallQual', 'Qualité générale'),
        ('YearBuilt',   'Année de construction'),
        ('TotalBsmtSF', 'Surface sous-sol (pi²)'),
    ]
    available_sc = [(c, l) for c, l in scatter_features if c in filtered.columns]

    sc_row1 = st.columns(2)
    sc_row2 = st.columns(2)
    grille  = [sc_row1[0], sc_row1[1], sc_row2[0], sc_row2[1]]

    for i, (col_name, label) in enumerate(available_sc):
        with grille[i]:
            fig = px.scatter(
                filtered, x=col_name, y='SalePrice',
                opacity=0.35,
                color_discrete_sequence=['coral'],
                labels={col_name: label, 'SalePrice': 'Prix ($)'},
                height=280
            )
            fig.update_layout(margin=dict(t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Ligne 3 : Heatmap + Biais ──
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Matrice de corrélation")
        corr_target = ['SalePrice', 'GrLivArea', 'TotalBsmtSF', 'OverallQual',
                       'OverallCond', 'YearBuilt', 'GarageCars', 'FullBath']
        corr_cols   = [c for c in corr_target if c in filtered.columns]
        corr_matrix = filtered[corr_cols].corr().round(2)
        fig = px.imshow(
            corr_matrix,
            color_continuous_scale='RdBu_r',
            zmin=-1, zmax=1,
            text_auto=True,
            height=380
        )
        fig.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("⚖️ Biais — Prix moyen par quartier")
        if 'Neighborhood' in train_df.columns:
            bias_df = (train_df.groupby('Neighborhood')['SalePrice']
                       .agg(['mean', 'count'])
                       .reset_index()
                       .sort_values('mean'))
            bias_df.columns = ['Quartier', 'Prix moyen ($)', 'Nb maisons']
            fig = px.bar(
                bias_df, x='Prix moyen ($)', y='Quartier',
                orientation='h',
                color='Prix moyen ($)',
                color_continuous_scale='Purples',
                labels={'Prix moyen ($)': 'Prix moyen ($)', 'Quartier': ''},
                height=380
            )
            fig.update_layout(margin=dict(t=20, b=20),
                               coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────
# ONGLET 3 – Données filtrées
# ───────────────────────────────
with tab3:
    st.header("📋 Données filtrées")
    st.caption(f"{len(filtered):,} lignes · {len(filtered.columns)} colonnes")

    if 'Neighborhood' in filtered.columns:
        neighborhoods = ['Tous'] + sorted(filtered['Neighborhood'].unique().tolist())
        selected_nb   = st.selectbox("Filtrer par quartier", neighborhoods)
        if selected_nb != 'Tous':
            filtered = filtered[filtered['Neighborhood'] == selected_nb]

    st.dataframe(filtered, use_container_width=True)
    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Télécharger les données filtrées",
                       csv, "filtered_data.csv", "text/csv")
