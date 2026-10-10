# Image Airflow de MobilityFlow : Airflow officiel + un environnement Python SÉPARÉ pour le pipeline.
# Pourquoi séparé ? dbt et Airflow demandent des versions de bibliothèques qui peuvent se
# contredire. Un environnement (venv) à part évite tout conflit et garde Airflow intact.
FROM apache/airflow:2.10.5

RUN python -m venv /home/airflow/pipeline-venv \
 && /home/airflow/pipeline-venv/bin/pip install --no-cache-dir pandas pyarrow duckdb dbt-duckdb