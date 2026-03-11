# 🏭 Industrial Data Automation & Standardization (Multi-Country Panels)

## 📌 Contexte

Projet d’automatisation et de standardisation de panels multi-pays (fichiers provenant de plusieurs sources).
_Un panel_ est un fichier Excel interne à l’équipe qui permet d’intégrer et de structurer les données des correspondants pays dans la base de données interne. Il contient notamment :

* Les informations commerciales par pays et par modèle
* Les marques et modèles de véhicules
* Le type de carburant (souvent à compléter manuellement)
* Les volumes de ventes

Ces données sont fournies par différents correspondants et doivent être harmonisées avant leur intégration dans une base de données interne d’analyse statistique.

💼 Objectif : fiabiliser et automatiser l’ingestion de ces panels dans l’outil interne de gestion de données de l’équipe statistique, pour limiter les erreurs manuelles, accélérer les mises à jour et faciliter le suivi multi-pays.

---

## 🧩 Problématique

* Données hétérogènes fournies par chaque correspondant pays → impossible analyse directe.
* Informations parfois incomplètes ou nécessitant vérification (carburant, nouveaux modèles…)
* Besoin de contrôle qualité strict avant intégration dans SIM
* Process manuel trop long et sujet à erreurs → nécessité d’automatisation et de reproductibilité

---

## ⚙️ Pipeline / Architecture

```mermaid
flowchart LR
A[Correspondants pays – fichiers sources] --> B[Création & Nettoyage du Panel - Excel interne]
B --> C[Validation & Standardisation]
C --> D[Intégration dans SIM & Analyse 📊]
```

## 🛠 Méthodologie

* Analyse des fichiers sources pour identifier champs critiques et divergences
* Création du panel interne Excel pour centraliser et standardiser les informations
* Écriture macros VBA pour nettoyage et consolidation
* Vérification des informations importantes : marques, modèles, carburant, volumes
* Structuration panels homogènes
* Validation et contrôle qualité
* Mise à jour régulière pour maintenir la base sur plusieurs années

💡 Points clés :

* Limitation des risques d’erreurs lors de l’intégration
* Process reproductible et industrialisé
* Standardisation multi-pays pour cohérence et fiabilité

---

## 📊 Exemple de dataset

**panel_FR.xlsx**

| ID  | Country | Brand   | Model | Fuel     | Sales |
| --- | ------- | ------- | ----- | -------- | ----- |
| 001 | FR      | Renault | Clio  | Gas      | 1200  |
| 002 | FR      | Renault | Zoe   | Electric | 45    |

---

## 🏆 Résultats / Livrables

* Panels standardisés multi-pays.
* Process automatisé réduisant significativement le temps et les erreurs
* Base SIM mise à jour avec données fiables sur plusieurs années
* Gains temps et fiabilité pour équipe Statistique.
 
---

## ⚠️ Limites & Perspectives
Certaines automatisations reposent sur des outils bureautiques.

Une évolution possible serait :

* migration vers des pipelines Python
* automatisation plus avancée du contrôle qualité

---

## 🔒 Confidentialité

Le projet respecte les principes de confidentialité industrielle et de protection des données.

---

## 📌 Ce que j’ai appris

* Industrialisation et automatisation de processus multi-pays
* Structuration et standardisation de données hétérogènes
* Gestion de l’intégration dans un outil interne statistique (SIM)
* Mise en place d’un suivi fiable et reproductible pour plusieurs années


