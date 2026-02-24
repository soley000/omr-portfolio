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
