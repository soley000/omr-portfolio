<a id="top"></a>

# MobilityFlow: Bike-Sharing Station Availability Platform

> An end-to-end data platform that turns a raw real-time bike-sharing feed into tested, decision-ready tables and a dashboard.

**[Overview](#overview)** · **[Architecture](#architecture)** · **[Data Pipeline](#data-pipeline)** · **[Data Quality](#data-quality)** · **[Dashboard](#dashboard)** · **[Installation](#installation)** · **[Limitations](#limitations)**

| | |
|---|---|
| **Problem** | The public bike-sharing feed shows only the current state of each station, keeps no history and contains unreliable records: an operations team cannot tell which stations lack bikes or docks, and when. |
| **Approach** | Collected the feed every minute, converted it to Parquet, built tested analytical tables with dbt in DuckDB, scheduled the chain with Airflow in Docker, and presented the answers in a Streamlit dashboard. |
| **Key result** | 107 stations collected every minute and processed by a nightly five-task pipeline with data tests; source data issues detected, documented and shown in the dashboard instead of hidden. |
| **Stack** | Python · Parquet · Airflow · dbt · DuckDB · Docker · Streamlit |
| **Context** | Open source |

## Overview

Bike-sharing feeds only expose the current state of each station. They keep no history, and they include stations that are closed or not installed, as well as values that cannot be trusted. The questions an operations team cares about stay unanswered:

* Which stations are often empty (no bike to take) or full (no dock to return a bike), and at what time of day?
* Where should bikes be moved, and which stations should be checked?
* Can the figures be trusted, and has the collection itself missed anything?

**MobilityFlow** collects the Bicloo feed (Nantes, France) continuously, builds the missing history and turns it into reliable tables and a dashboard that answers these questions.

## Objectives

* Collect the feed continuously and keep a complete, timestamped history.
* Clean and model the data into analytical tables with automated quality checks.
* Answer the operations questions in plain language, in a dashboard.
* Make data issues visible: gaps in the collection, suspicious stations, unreliable fields.
* Keep the whole project local, free and reproducible.

## Dataset

| | |
|---|---|
| Source | Bicloo / Naolib network, Nantes Métropole, operated by JCDecaux (GBFS 2.3) |
| Entry point | `https://api.cyclocity.fr/contracts/nantes/gbfs/gbfs.json` |
| Feeds used | `station_status` (every minute), `station_information` (refreshed every 6 hours), `system_information` (at start) |
| Size | 107 stations, one snapshot per minute, about 154,000 rows per day |
| History | Collected by this project since 9 October 2026 (the source keeps none) |
| Licence | Licence Ouverte (Etalab): version 1.0 on the JCDecaux developer site, version 2.0 in the national catalogue. Both require crediting the producer and the date of the last update (see Attribution). |

## Architecture

```mermaid
flowchart LR
    A["Bicloo<br/>GBFS API"] --> B["Collector<br/>(every minute)"]
    B --> C["Raw JSON"]
    C --> D["Parquet<br/>(one folder per day)"]
    D --> E["dbt<br/>models + tests"]
    E --> F[("DuckDB<br/>warehouse")]
    F --> G["Streamlit<br/>dashboard"]
```

Airflow runs the chain from the Parquet conversion to the published warehouse every night at 03:00 (Paris time), for the previous day. The dashboard only reads the published warehouse, in read-only mode.

A production setup would add a message queue (Kafka) and a stream-processing branch (PySpark) in front of a cloud warehouse (BigQuery). That direction is described here only. It is not built: the volume does not require it, and the project is meant to stay free and reproducible.

## Data Pipeline

<details>
<summary><b>The five Airflow tasks (DAG <code>mobilityflow_daily</code>)</b></summary>

| Task | What it does |
|---|---|
| `convert_to_parquet` | Turns the raw JSON files of one Paris day into Parquet. Can be re-run for any day. |
| `check_output` | Checks that the day's Parquet file exists and is not empty. |
| `dbt_run` | Rebuilds the analytical tables in a database local to the container. |
| `dbt_test` | Runs the data tests. A test in error fails the task; a warning does not block. |
| `publish_warehouse` | Copies the finished database to the shared data folder with an atomic replace. |

The database is built inside the container and then copied. DuckDB locks its file, and a Windows folder mounted in Docker can make that lock fail. Replacing the file in one step also means the dashboard never reads a half-written database, and a failed test leaves the previous database in place.

Each run processes the previous day. A manual run can target any day with `{"date": "YYYY-MM-DD"}`.

</details>

<details>
<summary><b>The dbt models</b></summary>

| Layer | Model | Content |
|---|---|---|
| Staging | `stg_station_status`, `stg_station_information` | Typed, cleaned tables built from the Parquet files (latest reference data per station) |
| Mart | `dim_station` | One row per station: position, declared and observed capacity, capacity gap flag, in service now |
| Mart | `fct_station_hour` | Per station and hour: bikes (average, minimum, maximum), share of time empty or full, fill rate |
| Mart | `fct_collection_hourly` | Per hour: snapshots received versus expected, to detect collection gaps |
| Mart | `fct_station_unchanged` | Longest and current period without any change, to flag stations that look frozen |

Tests cover uniqueness, value ranges, negative counts, duplicate snapshots, capacity consistency and valid coordinates. Known issues of the source are set to warnings on purpose, so they stay visible without blocking the pipeline.

</details>

## Data Quality

The raw feed cannot be used as it is. Each issue below was measured, then turned into a rule or a visible flag.

<details>
<summary><b>What the feed showed, and what was decided</b></summary>

| Finding | How it was established | Decision |
|---|---|---|
| `last_reported` does not measure freshness: 887 of 892 bike-count changes happened without it moving, and 96 of 107 stations never saw it change. | 100 consecutive snapshots | Kept in the Parquet files for information, used in no quality rule. |
| Some stations are not installed or closed for rental (3 and 2 in the snapshot checked). | One snapshot | Excluded from availability statistics and flagged. |
| For 5 stations out of 104, capacity does not match the sum of available and out-of-service bikes and docks, always by the same amount. | 152 snapshots | Declared and observed capacity are both kept, the gap is flagged, and fill rates use the observed value. The cause is not verified. |
| One station is reported at coordinates (0, 0). | Dashboard map check | Left out of the map, kept in the calculations, listed in the dashboard and covered by a dbt warning test. |
| The collector was off for part of an hour on 9 October. | Collection completeness table | Shown as a gap in the dashboard, not filled in. |

A station that looks frozen cannot be told apart with certainty from a station that is simply quiet. The dashboard says so.

</details>

## Dashboard

Four pages, written in plain language, reading the warehouse in read-only mode.

| Page | Role |
|---|---|
| Summary | Where to send bikes, what to check, and whether the figures can be trusted |
| When and where | Map of stations coloured by verdict, hourly profile, top stations, heatmap by hour |
| Data reliability | Collection gaps, capacity gaps, stations without valid coordinates, stations that look frozen |
| About | The problem, the pipeline, a short glossary and the limits |

A station is described as lacking bikes or docks when it is empty (or full) for at least 20 % of its in-service measurements over the chosen period. This threshold is a design choice and can be adjusted as the history grows.

## Technologies

| Category | Technologies |
|---|---|
| Language | Python 3.10+ |
| Collection | Python standard library (HTTP, JSON) |
| Storage | Parquet, DuckDB |
| Orchestration | Airflow 2.10 (standalone mode) |
| Transformation and tests | dbt (dbt-duckdb) |
| Environment | Docker, Docker Compose |
| Quality | pytest, GitHub Actions |
| Dashboard | Streamlit, Plotly, Folium |

<details>
<summary><b>Why these tools, and the simpler alternative</b></summary>

| Tool | Why here | Simpler alternative |
|---|---|---|
| Parquet | Compact columnar files, fast to read, one folder per day | JSON or CSV |
| Airflow | Scheduling, retries, visible task status, re-run of a given day | cron |
| dbt | Versioned models and data tests next to the SQL | Plain SQL scripts |
| DuckDB | Free, local, no account, one file | BigQuery sandbox (tables expire after 60 days) |
| Docker | Same environment for everyone, Airflow and dbt isolated from the host | Local installs |
| Streamlit | A dashboard in Python, close to the data | A BI tool |

</details>

## Installation

Requires Docker Desktop and Python 3.10+. Commands are for Windows PowerShell.

1. Start the collector and keep it running (one line per minute):

```powershell
python ingestion\collector.py --out C:\dev\mobilityflow-data
```

2. Start Airflow. The data folder defaults to `C:/dev/mobilityflow-data` and can be changed with `MOBILITYFLOW_DATA_DIR`:

```powershell
docker compose up -d --build
```

The interface is at `http://localhost:8080`, and the login is printed in the container logs at first start. The DAG runs every night at 03:00 and processes the previous day.

3. Start the dashboard:

```powershell
python -m pip install -r app\requirements.txt
python -m streamlit run app\streamlit_app.py
```

Raw file names use UTC time. Days are cut on Paris time.

<details>
<summary><b>Project structure</b></summary>

```text
real-time-mobility-data-platform/
├── ingestion/            # raw collector
├── pipeline/             # JSON to Parquet conversion and output check
├── dags/                 # Airflow DAG and failure alert
├── monitoring/           # health check (collector, collection, warehouse, failures)
├── tests/                # automated tests on generated data
├── dbt/                  # models, tests and macros
├── app/                  # Streamlit dashboard
├── exploration/          # data exploration scripts
├── docs/                 # notes and decisions
├── .streamlit/           # dashboard theme
├── docker-compose.yml
├── Dockerfile
├── .gitignore
└── README.md
```

</details>

## Evaluation

* The scripts and dbt models were tested on generated data covering several days, with deliberate issues: gaps, frozen stations and a station at (0, 0).
* These tests run automatically on every change through GitHub Actions (JSON to Parquet, dbt run and test, dashboard data access, health check) and check that each planted issue is detected.
* The full chain (five Airflow tasks, publication of the warehouse, reading by the dashboard) ran successfully on real collected data.
* The 20 % rule and the frozen-station rule are first choices based on the collected history, and can be reviewed as it grows.

## Deployment and Monitoring

* Everything runs locally in Docker. There is no cloud deployment.
* Data quality is monitored through the dbt tests, the output check and the dashboard's reliability page.
* Pipeline failures are visible in the Airflow interface and written to an alert log (`monitoring/failures.log` in the data folder).
* A health check (`monitoring/health_check.py`) reports whether the collector is alive, the last hour of collection is complete, the warehouse is up to date and no task has failed. There is no push notification.

Cost: 0 EUR. No cloud billing account is attached.

## Key Takeaways

* A feed can look complete and still be unreliable: only a collected history revealed that `last_reported` does not track freshness.
* Showing data issues is part of the product: the dashboard states gaps, capacity mismatches and invalid coordinates instead of hiding them.
* Building the database apart and replacing it in one step keeps the dashboard safe from half-written files and from failed runs.
* The right tool depends on the volume: at this scale, streaming tools would add complexity without answering the business questions.

## Limitations

* One network (Nantes). History starts on 9 October 2026 and grows only while the collector runs.
* The collector runs on a personal computer, so gaps happen when it is off. They are measured and shown, not hidden.
* Airflow runs in `standalone` mode with SQLite and the sequential executor: a learning setup, not a production one.
* A frozen station cannot be told apart with certainty from a quiet one.
* The cause of the capacity gap at 5 stations and of the (0, 0) coordinates is not verified.
* The `last_reported` field cannot be used to measure freshness.

## Future Improvements

* Add push notifications (email or chat) for pipeline failures and health-check results.
* Publish a frozen, public version of the dashboard with the final export.
* Review the 20 % and frozen-station thresholds after several weeks of history.
* Reuse the history for failure prediction and for a natural-language analyst.
* Add a streaming layer (Kafka) as an optional extension.

## Attribution

Data: Bicloo / Naolib network, Nantes Métropole, operated by JCDecaux, under Licence Ouverte (Etalab). Source: https://api.cyclocity.fr/contracts/nantes/gbfs/gbfs.json. The date of the last update is shown in the dashboard. This project is independent and is not approved or endorsed by Nantes Métropole or JCDecaux.

## Author

**Rosette-Michèle Otounga**
Data & AI Engineer · Data Engineering · Applied AI

* [LinkedIn](https://linkedin.com/in/rosette-michele)
* [Portfolio](https://github.com/soley000/omr-portfolio)

<p align="right"><a href="#top">↑ Back to top</a></p>