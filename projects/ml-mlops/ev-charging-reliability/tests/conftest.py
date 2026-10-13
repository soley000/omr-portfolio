"""Réglages communs à tous les tests (pytest lit ce fichier automatiquement)."""
from evrel.data.load import get_data_dir

# Ces tests lisent le vrai jeu de données (85 Mo, hors Git). Sur GitHub, il n'existe pas :
# on ne les collecte pas, et l'en-tête de pytest le signale.
REAL_DATA_TESTS = ["test_load.py"]
REAL_DATA_AVAILABLE = (get_data_dir() / "raw").exists()

if not REAL_DATA_AVAILABLE:
    collect_ignore = REAL_DATA_TESTS


def pytest_report_header(config):
    if REAL_DATA_AVAILABLE:
        return "Données réelles : présentes, tous les tests sont lancés"
    return f"Données réelles : absentes, tests ignorés : {', '.join(REAL_DATA_TESTS)}"