# ⚡ EV Charging Data Engineering for Grid Regulation

## 📌 Contexte

Projet sur **données véhicules électriques (EV)** pour régulation réseau RTE.
Objectif : transformer des données brutes en **indicateurs exploitables** tout en garantissant **anonymisation et confidentialité**, afin de répondre aux besoins métier pour la performance énergétique.

---

## 🧩 Problématique

Les questions métiers typiques incluent :

* Quels jours ou périodes voient **des trajets longs ou courts** ?
* Quels types de véhicules effectuent les **trajets les plus énergivores** ?
* Quelles batteries **consomment le plus**, ou perdent rapidement du SOC ?
* Comment **identifier les sessions complètes** de charge et leurs caractéristiques ?

💡 Mon rôle : **transformer ces questions en métriques précises** (durée, énergie, puissance, SOC) et construire des CSV anonymisés **strictement limités aux chiffres demandés**.

💼 Contraintes :

* **Anonymisation totale** : tous les IDs clients ou véhicules sont chiffrés.
* **Strict minimum** : ne fournir que les chiffres demandés, pas de nombre d’utilisateurs ou d’identifiants individuels.
* Respect de la confidentialité et des exigences RGPD / internes.

---

## ⚙️ Pipeline / Architecture

```mermaid
flowchart LR
A[GCP Buckets & Raw EV Data] --> B[Exploration & Data Quality]
B --> C[Data Cleaning & Normalization]
C --> D[SQL Cross-Join & Session Reconstruction]
D --> E[Indicators Computation & CSV 📊]
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

4. **Indicators Computation & CSV**

   * Calcul d’indicateurs simples et clairs : énergie consommée, puissance moyenne/max, durée de session, variation SOC.
   * Transformation des demandes métier en chiffres exploitables.
   * Export CSV **anonymisé**, strictement limité aux données demandées.

---

### 📊 Exemple de dataset (anonymisé)

**raw_ev.csv**

| timestamp        | vehicle_id_hash | soc_start | soc_end | power |
| ---------------- | --------------- | --------- | ------- | ----- |
| 2025-06-01 08:00 | VE_001_hash     | 20        | 80      | 22    |
| 2025-06-01 09:00 | VE_002_hash     | 50        | 90      | 11    |

---

### 🏆 Résultats / Livrables

* CSV **anonymisés** et sécurisés pour les partenaires.
* Sessions de charge complètes reconstruites et vérifiées.
* Indicateurs calculés pour répondre aux questions métier :

  * Longues sessions / trajets par jour ou par véhicule
  * Batteries les plus consommées
  * Durée, puissance, variation SOC
  * Synthèse pour analyses stratégiques et décisionnelles

---

### ⚠️ Limites & Perspectives

* Toutes les données demandées ont été livrées conformes et anonymisées.
* Les partenaires peuvent utiliser ces CSV pour leurs prévisions et analyses.
* Pas de limitations techniques identifiées à ce stade — toute demande complémentaire sera traitée si nécessaire.
---

### 🔒 Confidentialité

* **Aucun ID client ou véhicule exposé**.
* Seules les informations strictement nécessaires pour les indicateurs sont partagées.
* Données réelles Renault **non exposées**.

---

### 📌 Ce que j’ai appris

* Data engineering à grande échelle avec **contrainte de confidentialité stricte**.
* Transformation des demandes métier en indicateurs précis et exploitables.
* Croisement multi-tables SQL et reconstruction complète des sessions de charge.
* Structuration pipeline robuste et reproductible pour livraisons industrielles.


