import pandas as pd


def create_features(df):
    """Création de nouvelles features pertinentes pour la prédiction du prix"""
    df = df.copy()

    # Âge du logement (plus un logement est ancien, plus son prix peut varier)
    df["AgeLogement"] = 2025 - df["YearBuilt"]

    # Surface totale : somme de la surface habitable et du sous-sol
    # fillna(0) car certaines maisons n'ont pas de sous-sol
    df["SurfaceTotale"] = df["GrLivArea"] + df["TotalBsmtSF"].fillna(0)

    # Nombre total de salles de bain pondéré
    # Une salle de bain complète = 1, une demi-salle = 0.5
    df["NbSallesDeBain"] = df["FullBath"] + 0.5 * df["HalfBath"].fillna(0)

    # Suppression des colonnes originales devenues redondantes
    df.drop(["YearBuilt", "GrLivArea", "TotalBsmtSF"], axis=1, inplace=True)

    return df