# Livraison de données à RTE

## 📌 Contexte
Projet Data Engineering pour transformer et livrer des datasets fiables à RTE.
Objectif : traduire les besoins métier en pipeline SQL opérationnel.

## 🧩 Problématique
Les équipes métier ont besoin de données fiables et à jour.
Besoin d’un pipeline automatisé pour éviter erreurs manuelles.

## ⚙️ Pipeline / Architecture
```mermaid
graph LR
A[Requête métier] --> B[Extraction SQL]
B --> C[Transformation / nettoyage]
C --> D[Validation des données]
D --> E[Livraison dataset final]
```
🛠 Méthodologie

Analyse des besoins métier

Création de scripts SQL pour extraction et transformation

Vérification des données (contrôles qualité)

Livraison des datasets prêts à l’usage

📊 Dataset

Mini dataset simulé : 5 lignes

Colonnes : timestamp, voltage, current, power

🏆 Résultats / Livrables

Dataset fiable livré aux équipes métier
