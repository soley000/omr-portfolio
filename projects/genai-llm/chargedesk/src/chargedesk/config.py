"""Lecture de la configuration de ChargeDesk."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"


def load_config(path: Path | None = None) -> dict:
    with open(path or CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dir(cfg: dict, key: str) -> Path:
    paths = cfg["paths"]
    return Path(os.environ.get(paths[f"{key}_env"], paths[f"{key}_default"]))


def source_dir(cfg: dict) -> Path:
    """Dossier des sorties de ChargeTriage (lecture seule)."""
    return _dir(cfg, "source_dir")


def data_dir(cfg: dict) -> Path:
    """Dossier de travail de ChargeDesk."""
    return _dir(cfg, "data_dir")


def warehouse_path(cfg: dict) -> Path:
    return data_dir(cfg) / cfg["paths"]["warehouse"]