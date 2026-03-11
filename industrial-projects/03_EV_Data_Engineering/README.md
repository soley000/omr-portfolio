# ⚡ EV Charging Data Engineering for Grid Regulation

## 📌 Contexte

Projet de data engineering sur des **données télémétriques de véhicules électriques (EV)** en collaboration avec un partenaire du secteur énergétique.
Objectif : 
L’objectif est de transformer des données brutes de recharge et de conduite en **indicateurs analytiques exploitables** pour l’analyse énergétique.

Tout en garantissant **anonymisation et confidentialité**, ces analyses peuvent servir à mieux comprendre les usages, les cycles de recharge et certaines tendances liées à la consommation énergétique

---

## 🧩 Problématique

Les questions métiers typiques incluent :

* Quels jours ou périodes voient **des trajets longs ou courts** ?
* Quels types de véhicules effectuent les **trajets les plus énergivores** ?
* Quelles batteries **consomment le plus**, ou perdent rapidement du SOC ?
* Comment **identifier les sessions complètes** de charge et leurs caractéristiques ?

💡 Mon rôle : **transformer ces questions en métriques exploitables** 

---

💼 Contraintes :

* **anonymisation complète des données**

* uniquement **données agrégées**

* aucune information permettant d’identifier un utilisateur ou un véhicule

* respect strict des règles de confidentialité et du RGPD
---

## ⚙️ Pipeline / Architecture

```mermaid
flowchart LR
A[GCP Buckets & Raw EV Data] --> B[Exploration & Data Quality]
B --> C[Data Cleaning & Normalization]
C --> D[SQL Cross-Join & Session Reconstruction]
D --> E[Indicators Computation 📊]
```

### 🔹 Étapes détaillées

1. **Exploration & Data Quality**

   * Analyse des tables brutes pour identifier quelles colonnes et valeurs peuvent être utilisées.
   * Vérification cohérence, valeurs manquantes, doublons.

2. **Data Cleaning & Normalization**

   * Correction des anomalies.
   * Harmonisation des formats et unités.

3. **SQL Cross-Join & Session Reconstruction**

   * Croisement des tables de conduite et de charge pour reconstruire des sessions complètes.
   * Définition des métriques métier (ex : long trajet > X km ou Y minutes, batterie consommant > seuil).

4. **Indicators Computation **

   * Calcul d’indicateurs simples et clairs : énergie consommée, puissance moyenne/max, durée de session, variation SOC.
   * Transformation des demandes métier en chiffres exploitables.
   * Données**anonymisé**, strictement limité aux données demandées.

---

### 📊 Exemple de dataset (anonymisé)


| timestamp        | vehicle_id_hash | soc_start | soc_end | power |
| ---------------- | --------------- | --------- | ------- | ----- |
| 2025-06-01 08:00 | VE_001_hash     | 20        | 80      | 22    |
| 2025-06-01 09:00 | VE_002_hash     | 50        | 90      | 11    |

---

## 🏆 Résultats / Livrables

* Données **anonymisés** et sécurisés pour les partenaires.
* Sessions de charge complètes reconstruites et vérifiées.
* Indicateurs calculés pour répondre aux questions métier :

  * Longues sessions / trajets par jour ou par véhicule
  * Batteries les plus consommées
  * Durée, puissance, variation SOC
  * Synthèse pour analyses stratégiques et décisionnelles

---

## ⚠️ Limites & Perspectives

* Toutes les données demandées ont été livrées conformes et anonymisées.
* Les partenaires peuvent utiliser ces données pour leurs prévisions et analyses.
* Pas de limitations techniques identifiées à ce stade — toute demande complémentaire sera traitée si nécessaire.
---

## 🔒 Confidentialité & RGPD

* **Aucun ID client ou véhicule exposé**.
* Seules les informations strictement nécessaires pour les indicateurs sont partagées.
* Les données générées contiennent uniquement des indicateurs agrégés pour analyse métier.
* Respect des exigences du RGPD

---

## 📌 Ce que j’ai appris

* Data engineering à grande échelle avec **contrainte de confidentialité stricte**.
* Transformation des demandes métier en indicateurs précis et exploitables.
* Croisement multi-tables SQL et reconstruction complète des sessions de charge.
* Structuration pipeline robuste et reproductible pour livraisons industrielles.


