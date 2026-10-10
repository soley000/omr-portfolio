"""MobilityFlow - collecteur brut GBFS (Bicloo / Naolib, Nantes).

Interroge le flux station_status a intervalle regulier et archive chaque
reponse TELLE QUELLE (aucune transformation). Les corrections et le
nettoyage se feront plus tard, dans le pipeline.

Les donnees sont ecrites HORS du depot (et hors OneDrive) :
    --out C:\\dev\\mobilityflow-data
ou via la variable d'environnement MOBILITYFLOW_DATA_DIR.
Sans option, elles vont dans ./data/raw (ignore par Git).

Usage :
    python collector.py --out C:\\dev\\mobilityflow-data           # toutes les 60 s
    python collector.py --out C:\\dev\\mobilityflow-data --once    # test : un seul passage
    python collector.py --interval 120 --out C:\\dev\\mobilityflow-data
"""

import argparse
import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GBFS_INDEX = "https://api.cyclocity.fr/contracts/nantes/gbfs/gbfs.json"
USER_AGENT = "MobilityFlow-collector/0.1 (projet portfolio, usage non commercial)"
TIMEOUT_S = 15

log = logging.getLogger("collector")


def fetch_json(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return resp.read()


def discover_feeds() -> dict:
    """Lit gbfs.json (point d'entree GBFS) et renvoie {nom_du_flux: url}."""
    index = json.loads(fetch_json(GBFS_INDEX))
    lang = next(iter(index["data"]))  # ex. "fr"
    return {f["name"]: f["url"] for f in index["data"][lang]["feeds"]}


def save_raw(raw_dir: Path, feed: str, payload: bytes) -> Path:
    """Ecrit la reponse brute, partitionnee par date, nom = heure d'ingestion UTC."""
    now = datetime.now(timezone.utc)
    folder = raw_dir / feed / f"date={now:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{now:%H%M%S}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(payload)
    tmp.replace(target)  # ecriture atomique : pas de fichier a moitie ecrit
    return target


def collect_once(raw_dir: Path, feeds: dict, names: tuple) -> None:
    for name in names:
        try:
            path = save_raw(raw_dir, name, fetch_json(feeds[name]))
            log.info("%s -> %s", name, path)
        except Exception as exc:  # on journalise et on continue : un trou vaut mieux qu'un arret
            log.error("echec %s : %s", name, exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60, help="secondes entre deux collectes")
    parser.add_argument("--once", action="store_true", help="un seul passage puis arret")
    parser.add_argument(
        "--ref-interval",
        type=int,
        default=21600,
        help="secondes entre deux rafraichissements du referentiel des stations (defaut : 6 h)",
    )
    parser.add_argument(
        "--out",
        default=os.environ.get("MOBILITYFLOW_DATA_DIR", "data/raw"),
        help="dossier de destination des donnees brutes (hors OneDrive de preference)",
    )
    args = parser.parse_args()

    raw_dir = Path(args.out) / "gbfs" / "nantes"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("destination : %s", raw_dir.resolve())

    feeds = discover_feeds()
    log.info("flux decouverts : %s", ", ".join(feeds))

    # Le referentiel des stations change rarement mais PEUT changer (station ouverte, fermee,
    # renommee) : on le recupere au demarrage, puis toutes les --ref-interval secondes.
    collect_once(raw_dir, feeds, ("station_information", "system_information"))
    last_reference = time.monotonic()

    while True:
        collect_once(raw_dir, feeds, ("station_status",))
        if args.once:
            break
        if time.monotonic() - last_reference >= args.ref_interval:
            collect_once(raw_dir, feeds, ("station_information",))
            last_reference = time.monotonic()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
