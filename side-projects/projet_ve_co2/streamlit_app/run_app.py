# -*- coding: utf-8 -*-
"""
Application Streamlit : Conseiller CO₂ personnalisé – Thermique vs VE
Auteure : Rosette-Michèle Otounga

Lancement : streamlit run run_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ─── CONFIGURATION PAGE ──────────────────────────────────────────────
st.set_page_config(
    page_title="Conseiller CO₂ – VE vs Thermique",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .card-rouge {
        background: #fff5f5;
        border-left: 5px solid #c62828;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 6px 0;
    }
    .card-vert {
        background: #f1f8f1;
        border-left: 5px solid #2e7d32;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 6px 0;
    }
    .card-bleu {
        background: #f0f4ff;
        border-left: 5px solid #1565c0;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 6px 0;
    }
    .chiffre { font-size: 2rem; font-weight: 700; }
    .label   { font-size: 0.85rem; color: #666; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES CO₂ ──────────────────────────────────────────────────
# Source : ADEME + calcul cycle de vie
CO2_VE_USAGE        = 49.33   # g/km (ADEME mesuré)
CO2_VE_FABRICATION  = 83.33   # g/km (12 500 kg / 150 000 km)
CO2_VE_TOTAL_G      = CO2_VE_USAGE + CO2_VE_FABRICATION  # 132.66 g/km
NB_VOITURES_FRANCE  = 38_000_000
KM_AN_MOYEN         = 13_000  # INSEE

# Facteurs d'émission par litre de carburant (ADEME)
FACTEURS_CO2 = {
    "Essence (SP95 / E10)": 2.31,
    "Diesel"              : 2.68,
    "Superéthanol E85"    : 1.61,
    "GPL"                 : 1.82,
    "Autre"               : 2.50,
}

# ─── CHARGEMENT FORECAST ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def charger_forecast():
    """
    Charge forecast_prophet.csv avec gestion robuste des chemins.
    La colonne 'annee' est forcée en entier.
    """
    chemins = [
        "forecast_prophet.csv",
        os.path.join(os.path.dirname(__file__), "forecast_prophet.csv"),
    ]
    for chemin in chemins:
        if os.path.exists(chemin):
            df = pd.read_csv(chemin, encoding='utf-8')
            # Forcer annee en entier (évite les bugs de filtrage)
            df['annee'] = pd.to_numeric(df['annee'], errors='coerce').astype(int)
            return df
    return None

df_forecast = charger_forecast()

# ─── TITRE ───────────────────────────────────────────────────────────
st.title("🌍 Conseiller CO₂ — Thermique vs Véhicule Électrique")
st.markdown(
    "*Estimez votre empreinte carbone automobile et visualisez l'impact "
    "collectif de la transition VE en France.*"
)
st.divider()

# ─── SIDEBAR : PARAMÈTRES UTILISATEUR ────────────────────────────────
with st.sidebar:
    st.header("⚙️ Votre profil")
    st.markdown("---")

    carburant = st.selectbox(
        "🔧 Type de carburant actuel",
        options=list(FACTEURS_CO2.keys())
    )

    conso = st.slider(
        "⛽ Consommation (L/100 km)",
        min_value=3.0, max_value=20.0, value=7.0, step=0.5,
        help="Consommation mixte de votre véhicule actuel"
    )

    km_an = st.number_input(
        "📍 Kilomètres par an",
        min_value=1_000, max_value=100_000, value=15_000, step=500
    )

    annee_ve = st.selectbox(
        "📅 Année de passage au VE",
        options=list(range(2024, 2036)),
        index=0,
        help="À partir de quand souhaitez-vous passer au VE ?"
    )

    scenario = st.radio(
        "📊 Scénario d'adoption nationale",
        options=["Conservateur", "Réaliste", "Ambitieux"],
        index=1,
        help=(
            "**Conservateur** : politiques timides (70% de la prédiction)\n\n"
            "**Réaliste** : prédiction Prophet\n\n"
            "**Ambitieux** : bonus et incitations fortes (140%)"
        )
    )

    st.markdown("---")
    st.caption("Sources : ADEME · data.gouv.fr · Our World in Data · Prophet (Meta)")

# ─── CALCULS INDIVIDUELS ─────────────────────────────────────────────
facteur         = FACTEURS_CO2[carburant]
emission_th_kg  = conso * km_an / 100 * facteur          # kg CO₂/an
emission_ve_kg  = CO2_VE_TOTAL_G * km_an / 1_000         # kg CO₂/an
gain_kg         = emission_th_kg - emission_ve_kg         # kg CO₂/an
gain_t          = gain_kg / 1_000                         # tonnes CO₂/an
arbres          = gain_kg / 25                            # 25 kg CO₂/arbre/an
reduction_pct   = gain_kg / emission_th_kg * 100 if emission_th_kg > 0 else 0

# Seuil de rentabilité environnementale
# = CO₂ fabrication VE / gain par km à l'usage uniquement
gain_usage_seul = (emission_th_kg / km_an * 1000) - CO2_VE_USAGE
km_rentabilite  = 12_500_000 / gain_usage_seul if gain_usage_seul > 0 else None
ans_rentabilite = km_rentabilite / km_an if km_rentabilite else None

# ─── SECTION 1 : BILAN INDIVIDUEL ────────────────────────────────────
st.header("1. 📊 Votre bilan CO₂ individuel")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="card-rouge">
        <div class="label">🚗 {carburant} — émissions actuelles</div>
        <div class="chiffre" style="color:#c62828;">{emission_th_kg:,.0f} kg</div>
        <div class="label">CO₂ par an</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="card-vert">
        <div class="label">🔌 Véhicule électrique équivalent</div>
        <div class="chiffre" style="color:#2e7d32;">{emission_ve_kg:,.0f} kg</div>
        <div class="label">CO₂ par an (usage + fabrication)</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="card-bleu">
        <div class="label">✅ Votre gain annuel</div>
        <div class="chiffre" style="color:#1565c0;">{gain_kg:,.0f} kg</div>
        <div class="label">≈ {arbres:.0f} arbres plantés / an</div>
    </div>""", unsafe_allow_html=True)

# Message principal
if gain_kg > 0:
    st.success(
        f"🌱 En passant au VE, vous réduisez vos émissions automobiles de "
        f"**{reduction_pct:.0f}%** — soit **{gain_t:.2f} tonne(s) de CO₂ économisées par an**."
    )
    if km_rentabilite and ans_rentabilite:
        st.info(
            f"🏁 Rentabilité environnementale atteinte après **{km_rentabilite:,.0f} km** "
            f"≈ **{ans_rentabilite:.1f} ans** à votre rythme de {km_an:,} km/an."
        )
else:
    st.warning("⚠️ Avec ce profil, le gain net est faible — vérifiez la consommation saisie.")

st.divider()

# ─── SECTION 2 : PROJECTIONS NATIONALES ──────────────────────────────
st.header("2. 🇫🇷 Projections nationales (Prophet)")

if df_forecast is None:
    st.error(
        "⚠️ Fichier `forecast_prophet.csv` introuvable. "
        "Lancez d'abord le notebook `02_modelisation_prediction_co2.ipynb`."
    )
else:
    # Mapping scénario → colonne
    MAP_SCENARIO = {
        "Conservateur": "scenario_conservateur",
        "Réaliste"    : "scenario_realiste",
        "Ambitieux"   : "scenario_ambitieux",
    }
    MAP_CO2 = {
        "Conservateur": "co2_evite_conservateur_t",
        "Réaliste"    : "co2_evite_realiste_t",
        "Ambitieux"   : "co2_evite_ambitieux_t",
    }

    col_scenario = MAP_SCENARIO[scenario]
    col_co2      = MAP_CO2[scenario]

    # Fallback si colonnes manquantes
    if col_scenario not in df_forecast.columns:
        col_scenario = 'yhat'
    if col_co2 not in df_forecast.columns:
        col_co2 = 'co2_evite_total_tonnes'

    df_viz = df_forecast[
        (df_forecast['annee'] >= 2010) & (df_forecast['annee'] <= 2035)
    ].copy()

    # ── Graphique 1 : Part de marché VE ──────────────────────────────
    fig1 = go.Figure()

    # Intervalle de confiance
    if 'yhat_upper' in df_viz.columns and 'yhat_lower' in df_viz.columns:
        fig1.add_trace(go.Scatter(
            x=list(df_viz['annee']) + list(df_viz['annee'])[::-1],
            y=list(df_viz['yhat_upper'] * 100) + list(df_viz['yhat_lower'] * 100)[::-1],
            fill='toself',
            fillcolor='rgba(46, 125, 50, 0.12)',
            line=dict(color='rgba(0,0,0,0)'),
            name='Intervalle 80%',
            showlegend=True
        ))

    # Prédiction
    fig1.add_trace(go.Scatter(
        x=df_viz['annee'],
        y=df_viz[col_scenario] * 100,
        mode='lines+markers',
        name=f'Part VE — {scenario}',
        line=dict(color='#2e7d32', width=3),
        marker=dict(size=6)
    ))

    # Ligne de séparation
    fig1.add_vline(
        x=2023.5, line_dash='dash', line_color='gray', opacity=0.5,
        annotation_text='Prédictions →',
        annotation_position='top right'
    )

    fig1.update_layout(
        title=f'Part de marché VE nationale — Scénario {scenario}',
        xaxis_title='Année',
        yaxis_title='Part de marché (%)',
        hovermode='x unified',
        height=420,
        plot_bgcolor='white',
        yaxis=dict(gridcolor='#f0f0f0', ticksuffix='%'),
        xaxis=dict(gridcolor='#f0f0f0'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    st.plotly_chart(fig1, use_container_width=True)

    # ── Graphique 2 : Émissions collectives ──────────────────────────
    part_ve_viz      = df_viz[col_scenario].clip(lower=0)
    nb_ve_viz        = part_ve_viz * NB_VOITURES_FRANCE
    nb_th_viz        = NB_VOITURES_FRANCE - nb_ve_viz

    # CO₂ mix (votre profil × parc)
    co2_mix = (
        nb_ve_viz * CO2_VE_TOTAL_G * km_an +
        nb_th_viz * (emission_th_kg / km_an * 1000) * km_an
    ) / 1_000_000_000  # milliards de kg → millions de tonnes

    co2_tout_th = (NB_VOITURES_FRANCE * emission_th_kg) / 1_000_000_000

    fig2 = go.Figure()

    fig2.add_trace(go.Scatter(
        x=df_viz['annee'],
        y=[co2_tout_th] * len(df_viz),
        mode='lines',
        name='Sans adoption VE (référence)',
        line=dict(color='#c62828', width=2, dash='dash')
    ))

    fig2.add_trace(go.Scatter(
        x=df_viz['annee'],
        y=co2_mix,
        mode='lines+markers',
        name=f'Avec adoption VE — {scenario}',
        line=dict(color='#2e7d32', width=3),
        fill='tonexty',
        fillcolor='rgba(46, 125, 50, 0.12)',
        marker=dict(size=5)
    ))

    fig2.add_vline(x=2023.5, line_dash='dash', line_color='gray', opacity=0.5)

    fig2.update_layout(
        title='Émissions CO₂ du parc automobile français (millions de tonnes/an)',
        xaxis_title='Année',
        yaxis_title='Millions de tonnes CO₂/an',
        hovermode='x unified',
        height=420,
        plot_bgcolor='white',
        yaxis=dict(gridcolor='#f0f0f0'),
        xaxis=dict(gridcolor='#f0f0f0'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ─── SECTION 3 : IMPACT COLLECTIF ────────────────────────────────────
st.header("3. 🌱 Et si les nouvelles immatriculations suivaient votre exemple ?")

# ── Note méthodologique ───────────────────────────────────────────────
st.caption(
    "📌 **Note de lecture** — La part de marché VE mesure la proportion de véhicules électriques "
    "parmi les **nouvelles immatriculations annuelles** (voitures neuves vendues), "
    "et non la part du parc total en circulation. "
    "Le graphique ci-dessous simule : si ce pourcentage de nouveaux acheteurs chaque année "
    "faisait le même choix que vous, combien de CO₂ serait évité à l'échelle nationale ?"
)

if df_forecast is not None:
    df_col = df_viz.copy()
    part   = df_col[col_scenario].clip(lower=0)

    # CO₂ évité : part des nouvelles immat × parc total × gain individuel
    # (approximation : on applique le taux d'immatriculation au parc total)
    gain_individuel_g_km = max(0, (emission_th_kg / km_an * 1000) - CO2_VE_TOTAL_G)
    df_col['co2_evite_vous_t'] = (
        part * NB_VOITURES_FRANCE * gain_individuel_g_km * km_an / 1_000_000
    ).clip(lower=0)
    df_col['co2_evite_cumule_vous_t'] = df_col['co2_evite_vous_t'].cumsum()

    fig3 = go.Figure()

    fig3.add_trace(go.Bar(
        x=df_col['annee'],
        y=df_col['co2_evite_vous_t'] / 1_000_000,
        name='CO₂ évité / an',
        marker_color='#66bb6a',
        opacity=0.75
    ))

    fig3.add_trace(go.Scatter(
        x=df_col['annee'],
        y=df_col['co2_evite_cumule_vous_t'] / 1_000_000,
        name='Cumulé',
        mode='lines+markers',
        line=dict(color='#1b5e20', width=2.5),
        marker=dict(size=5),
        yaxis='y2'
    ))

    fig3.add_vline(x=2023.5, line_dash='dash', line_color='gray', opacity=0.5)

    fig3.update_layout(
        title=f'CO₂ évité si les nouvelles immatriculations adoptaient votre profil — {scenario}',
        xaxis_title='Année',
        hovermode='x unified',
        height=430,
        plot_bgcolor='white',
        yaxis=dict(title='Millions de tonnes CO₂/an', gridcolor='#f0f0f0'),
        yaxis2=dict(
            title='Cumulé (millions de tonnes)',
            overlaying='y', side='right', showgrid=False
        ),
        xaxis=dict(gridcolor='#f0f0f0'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    st.plotly_chart(fig3, use_container_width=True)

    co2_2035 = df_col[df_col['annee'] == 2035]['co2_evite_cumule_vous_t'].values
    if len(co2_2035) > 0 and co2_2035[0] > 0:
        part_2035 = df_col[df_col['annee'] == 2035][col_scenario].values[0] * 100
        st.success(
            f"🌍 Si **{part_2035:.0f}%** des nouvelles immatriculations en 2035 étaient électriques "
            f"avec votre profil de conduite, la France aurait évité "
            f"**{co2_2035[0]/1_000_000:.1f} millions de tonnes de CO₂** cumulées depuis 2010 "
            f"(scénario {scenario.lower()})."
        )

st.divider()

# ─── SECTION 4 : DEPUIS VOTRE PASSAGE AU VE ──────────────────────────
st.header("4. 📅 Votre bilan depuis le passage au VE")

annee_courante = 2026
if annee_ve <= annee_courante:
    annees_ecoulees = annee_courante - annee_ve
    co2_cumule_vous = gain_kg * annees_ecoulees
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric(
            label=f"CO₂ économisé depuis {annee_ve} ({annees_ecoulees} an{'s' if annees_ecoulees > 1 else ''})",
            value=f"{co2_cumule_vous:,.0f} kg",
            delta=f"≈ {co2_cumule_vous/25:.0f} arbres plantés"
        )
    with col_b:
        st.metric(
            label="Économie annuelle",
            value=f"{gain_kg:,.0f} kg CO₂/an",
            delta=f"{reduction_pct:.0f}% de réduction"
        )
else:
    restant = annee_ve - annee_courante
    st.info(
        f"📆 Dans **{restant} an{'s' if restant > 1 else ''}** vous passerez au VE — "
        f"vous économiserez **{gain_kg:,.0f} kg de CO₂/an** dès ce moment."
    )

# ─── PIED DE PAGE ─────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#888; font-size:0.82rem; line-height:1.8;">
    Application réalisée par <strong>Rosette-Michèle Otounga</strong><br>
    Sources : ADEME · data.gouv.fr · Our World in Data · Modélisation Prophet (Meta)<br>
    <a href="https://github.com/soley000" target="_blank">GitHub</a> ·
    <a href="https://linkedin.com/in/rosette-michele" target="_blank">LinkedIn</a> ·
    <a href="https://github.com/soley000/omr-portfolio" target="_blank">Portfolio</a>
</div>
""", unsafe_allow_html=True)
