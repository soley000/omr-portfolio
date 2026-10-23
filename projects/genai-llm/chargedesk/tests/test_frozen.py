"""Le jeu d'evaluation est fige : toute modification fait echouer ce test.

Si une question doit vraiment changer (bug dans une requete), on le
documente dans le README, on recalcule expected.json et on met a jour
l'empreinte dans config.yaml, en le disant. Jamais en silence.
"""
import json

import pytest

from chargedesk.config import load_config
from chargedesk.eval.build_expected import EXPECTED_PATH, sha256_file
from chargedesk.eval.questions import QUESTIONS_PATH


def test_questions_file_is_frozen():
    frozen = load_config()["evaluation"]["frozen_questions_sha256"]
    assert sha256_file(QUESTIONS_PATH) == frozen


def test_expected_answers_match_the_frozen_questions():
    if not EXPECTED_PATH.exists():
        pytest.skip("expected.json absent")
    data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert data["questions_sha256"] == sha256_file(QUESTIONS_PATH)
    assert len(data["items"]) == 62
