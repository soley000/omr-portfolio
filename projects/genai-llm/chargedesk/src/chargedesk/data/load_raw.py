"""Chargement des sorties de ChargeTriage dans l'entrepot DuckDB (schema raw).

Les fichiers sources sont lus, jamais modifies. Tout est verifie avant
d'ecrire : si une source manque ou n'a pas le nombre de lignes attendu,
rien n'est ecrit. Chaque chargement est note dans raw.load_log (source,
chemin, empreinte SHA-256, lignes, date) : c'est la provenance que
ChargeDesk citera dans ses reponses.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from chargedesk.config import load_config, source_dir, warehouse_path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_source(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"format non pris en charge : {path.name}")


def load_raw(
    src_dir: Path,
    warehouse: Path,
    sources: dict[str, str],
    expected_rows: dict[str, int] | None = None,
) -> pd.DataFrame:
    expected_rows = expected_rows or {}

    # 1. Tout lire et tout verifier avant d'ecrire
    frames: dict[str, pd.DataFrame] = {}
    log = []
    for name, rel in sources.items():
        path = src_dir / rel
        if not path.exists():
            raise FileNotFoundError(f"source manquante : {path}")
        df = read_source(path)
        expected = expected_rows.get(name)
        if expected is not None and len(df) != expected:
            raise ValueError(f"{name} : {len(df)} lignes, {expected} attendues")
        frames[name] = df
        log.append({
            "source": name,
            "path": str(path),
            "sha256": sha256(path),
            "rows": len(df),
            "loaded_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })

    # 2. Ecrire dans l'entrepot
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for name, df in frames.items():
            con.register("_df", df)
            con.execute(f"CREATE OR REPLACE TABLE raw.{name} AS SELECT * FROM _df")
            con.unregister("_df")
        log_df = pd.DataFrame(log)
        con.register("_log", log_df)
        con.execute("CREATE OR REPLACE TABLE raw.load_log AS SELECT * FROM _log")
        con.unregister("_log")
    finally:
        con.close()
    return log_df


def main() -> None:
    cfg = load_config()
    log = load_raw(source_dir(cfg), warehouse_path(cfg), cfg["sources"], cfg.get("expected_rows"))
    log["sha256"] = log["sha256"].str[:12]
    print(log[["source", "rows", "sha256"]].to_string(index=False))
    print("entrepot :", warehouse_path(cfg))


if __name__ == "__main__":
    main()