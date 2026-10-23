"""Journal de surveillance : une ligne JSON par question posee a l'API.

Ce qui est note : l'heure (UTC), le soir choisi, la question (tronquee), reponse preparee ou en direct,
le statut, le modele, la bascule vers le repli, les incidents, le temps, les appels LLM, les jetons, les outils.
Ce qui n'est PAS note : adresse IP, navigateur, identite. La question est gardee pour savoir ce que les
visiteurs demandent ; la page previent qu'il ne faut pas y ecrire d'information personnelle.

Le journal est ecrit dans un fichier ET sur la sortie standard : sur Render (disque non conserve entre deux
redemarrages), ce sont les journaux du service qui gardent la trace.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("chargedesk.journal")
if not log.handlers:                      # une ligne par question sur la sortie standard (journaux Render)
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("chargedesk.journal %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


class Journal:
    def __init__(self, path: Path | str | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self.counts: Counter = Counter()          # depuis le demarrage du serveur, pour /stats
        self.started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def record(self, event: dict) -> dict:
        event = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **event}
        line = json.dumps(event, ensure_ascii=False, default=str)
        with self._lock:
            self.counts["questions"] += 1
            self.counts[f"source_{event.get('source')}"] += 1
            self.counts[f"http_{event.get('http')}"] += 1
            if event.get("fallback_used"):
                self.counts["fallback"] += 1
            if self.path:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                except OSError as exc:           # un journal qui echoue ne doit jamais casser une reponse
                    log.warning("journal non ecrit : %s", exc)
        log.info("question %s", line)
        return event

    def stats(self) -> dict:
        c = self.counts
        n = c["questions"]
        return {"since": self.started, "questions": n,
                "prepared": c["source_preparee"], "live": c["source_direct"],
                "ok": c["http_200"], "unavailable": c["http_503"], "daily_limit": c["http_429"],
                "fallback": c["fallback"]}
