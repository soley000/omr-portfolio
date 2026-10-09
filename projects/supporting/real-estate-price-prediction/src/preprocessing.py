import pandas as pd
import numpy as np


def handle_missing_values(df):
    """Imputation des valeurs manquantes"""
    df = df.copy()

    num_cols = df.select_dtypes(include=np.number).columns
    cat_cols = df.select_dtypes(include="object").columns

    # Numériques → médiane
    for col in num_cols:
        df[col] = df[col].fillna(df[col].median())

    # Catégorielles → 'None' (ex: pas de garage, pas de piscine)
    for col in cat_cols:
        df[col] = df[col].fillna("None")

    return df


def remove_outliers_iqr(df, column):
    """Supprime les outliers selon la méthode IQR"""
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    df_clean = df[(df[column] >= lower) & (df[column] <= upper)].reset_index(drop=True)
    removed = len(df) - len(df_clean)
    print(f"  [remove_outliers_iqr] '{column}' : {removed} outlier(s) supprimé(s)")
    return df_clean


def encode_categorical(df):
    """Encodage one-hot des colonnes catégorielles"""
    df = pd.get_dummies(df, drop_first=True)
    return df