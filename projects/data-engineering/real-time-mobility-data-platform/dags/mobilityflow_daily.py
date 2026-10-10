"""DAG MobilityFlow : chaque jour à 03h00 (Paris), traite la VEILLE.

  convert_to_parquet -> check_output -> dbt_run -> dbt_test -> publish_warehouse

1. convert_to_parquet : JSON bruts -> Parquet du jour (script relançable)
2. check_output       : le Parquet du jour existe et n'est pas vide
3. dbt_run            : reconstruit les tables d'analyse dans une base LOCALE au conteneur
4. dbt_test           : exécute les tests qualité (un test en ERREUR fait échouer la tâche ;
                        un simple avertissement ne bloque pas)
5. publish_warehouse  : copie la base terminée vers <données>/warehouse/ (remplacement atomique)

Alerte : si une tâche échoue pour de bon, une ligne est ajoutée à <données>/monitoring/failures.log
(voir mobilityflow_alerts.py ; le script monitoring/health_check.py la lit).

Pourquoi construire la base dans le conteneur puis la copier ? DuckDB verrouille son fichier ;
sur un dossier Windows monté dans Docker ce verrou peut échouer, et on évite aussi qu'Airflow
et toi écriviez en même temps. Si les tests échouent, rien n'est publié : l'ancienne base reste.
"""
import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

from mobilityflow_alerts import log_failure  # écrit une ligne dans le journal d'alertes quand une tâche échoue

PY = "/home/airflow/pipeline-venv/bin/python"
DBT = "/home/airflow/pipeline-venv/bin/dbt"

# Jour de Paris à traiter :
#  - par défaut, début de l'intervalle du run (la VEILLE pour un run de 03h00 ;
#    attention : un déclenchement manuel traite lui aussi le dernier intervalle COMPLET) ;
#  - ou un jour choisi à la main : Trigger DAG w/ config  ->  {"date": "2026-10-09"}
PARIS_DAY = (
    "{{ (dag_run.conf or {}).get('date') or "
    "data_interval_start.in_timezone('Europe/Paris').strftime('%Y-%m-%d') }}"
)

with DAG(
    dag_id="mobilityflow_daily",
    description="JSON bruts -> Parquet -> tables dbt testées -> base publiée",
    start_date=pendulum.datetime(2026, 10, 9, tz="Europe/Paris"),
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=5),
        "on_failure_callback": log_failure,   # appelée quand une tâche a échoué pour de bon (après ses 2 reprises)
    },
    tags=["mobilityflow"],
) as dag:
    convert = BashOperator(
        task_id="convert_to_parquet",
        bash_command=f"{PY} /opt/airflow/pipeline/json_to_parquet.py --data /data --date {PARIS_DAY}",
    )
    check = BashOperator(
        task_id="check_output",
        bash_command=f"{PY} /opt/airflow/pipeline/check_output.py --data /data --date {PARIS_DAY}",
    )
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"mkdir -p /tmp/warehouse && cd /opt/airflow/dbt && {DBT} run --profiles-dir .",
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd /opt/airflow/dbt && {DBT} test --profiles-dir .",
    )
    publish = BashOperator(
        task_id="publish_warehouse",
        bash_command=(
            "mkdir -p /data/warehouse "
            "&& cp /tmp/warehouse/mobilityflow.duckdb /data/warehouse/mobilityflow.duckdb.tmp "
            "&& mv -f /data/warehouse/mobilityflow.duckdb.tmp /data/warehouse/mobilityflow.duckdb"
        ),
    )
    convert >> check >> dbt_run >> dbt_test >> publish