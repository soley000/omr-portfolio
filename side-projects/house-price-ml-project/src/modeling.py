from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error


def train_linear_regression(X_train, y_train):
    """
    Entraîne un modèle de Régression Linéaire.

    X_train : variables explicatives d'entraînement
    y_train : variable cible d'entraînement
    """
    model = LinearRegression()
    model.fit(X_train, y_train)
    return model


def train_random_forest(X_train, y_train):
    """
    Entraîne un modèle Random Forest (ensemble d'arbres de décision).

    - n_estimators : nombre d'arbres
    - max_depth    : profondeur maximale de chaque arbre
    """
    model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    return model


def train_gradient_boosting(X_train, y_train):
    """
    Entraîne un modèle Gradient Boosting.

    Chaque arbre apprend à corriger les erreurs de l'arbre précédent.
    """
    model = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                      max_depth=4, random_state=42)
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test):
    """
    Évalue un modèle sur un jeu de test.

    Retourne :
    - r2  : R² score (capacité du modèle à expliquer la variance)
    - mae : Mean Absolute Error (erreur moyenne en dollars)
    """
    predictions = model.predict(X_test)
    r2  = r2_score(y_test, predictions)
    mae = mean_absolute_error(y_test, predictions)
    return r2, mae