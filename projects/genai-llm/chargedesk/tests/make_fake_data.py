"""Cree un dossier de donnees FICTIVES (meme structure que les vraies) pour construire l'image en CI.

    python tests/make_fake_data.py <dossier>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conftest import make_warehouse  # noqa: E402

out = Path(sys.argv[1])
(out / "demo").mkdir(parents=True, exist_ok=True)
make_warehouse(out / "chargedesk.duckdb")
(out / "demo" / "prepared.json").write_text(json.dumps({"version": 1, "items": {}}), encoding="utf-8")
print("donnees fictives :", out)
