"""API ChargeDesk avec un faux LLM : aucune cle, aucun appel reseau (comme en CI)."""
import json
import re

import pytest
import yaml
from fastapi.testclient import TestClient

from api.main import create_app
from api.service import Desk
from api.templates import FREQUENT, all_rendered
from chargedesk.config import PROJECT_ROOT
from chargedesk.llm.client import LLMResponse, QuotaExhausted


class FakeLLM:
    """1er tour : demande la liste du soir ; 2e tour : repond avec le score de la 1re borne."""
    def __init__(self):
        self.turn = 0

    def chat(self, messages, tools=None, rep=0):
        self.turn += 1
        if self.turn % 2 == 1:
            return LLMResponse(content=None, tool_calls=[{"id": "c1", "name": "get_evening_list", "arguments": "{}"}],
                               prompt_tokens=10, completion_tokens=5, latency_s=0.01, cached=False, model="fake")
        result = json.loads(messages[-1]["content"])
        top = result["list"][0]
        return LLMResponse(content=json.dumps({
            "status": "answered", "text": f"Borne {top['post_id']} en tete.", "sources": ["get_evening_list"],
            "figures": [{"name": "score", "value": top["score"], "unit": "score"}]}),
            tool_calls=[], prompt_tokens=10, completion_tokens=5, latency_s=0.01, cached=False, model="fake")


class DownLLM:
    def chat(self, *a, **k):
        raise QuotaExhausted("quota du jour")


def client(fake_warehouse, factory=lambda name: FakeLLM(), **kw):
    return TestClient(create_app(Desk(fake_warehouse, factory, **kw)))


def test_health_and_page(fake_warehouse):
    c = client(fake_warehouse)
    assert c.get("/health").json()["status"] == "ok"
    page = c.get("/")
    assert page.status_code == 200 and "ChargeDesk" in page.text


def test_meta_gives_questions_and_chargetriage_link(fake_warehouse):
    m = client(fake_warehouse).get("/meta").json()
    assert len(m["frequent"]) == len(FREQUENT) and m["post_questions"] and m["site_questions"]
    assert m["chargetriage_url"].startswith("https://") and m["first_evening"] == "2021-08-31"
    assert m["coverage"]["data_start"] == "2020-01-01" and m["coverage"]["data_end"] == "2021-12-31"
    assert m["coverage"]["n_posts"] > 0 and m["coverage"]["n_sites"] > 0


def test_evening_view_shows_list_and_silent_sites_outside_it(fake_warehouse):
    d = client(fake_warehouse).get("/evening/2021-10-05").json()
    assert len(d["list"]) == 10 and d["list"][0]["post_id"] == 23
    assert 0 <= d["reliability"]["champion"] <= 1 and d["reliability_evenings"].endswith("2021-10-04")
    silent = {s["site"]: s for s in d["silent_sites"]}
    assert "Technology Park" in silent                      # muettes depuis le 29/09 dans l'entrepot fictif
    listed = {r["post_id"] for r in d["list"]}
    assert not any(p in listed for s in d["silent_sites"] for p in s["posts"])


def test_evening_view_never_sees_after_the_evening(fake_warehouse):
    before = client(fake_warehouse).get("/evening/2021-09-27").json()
    assert "Technology Park" not in {s["site"] for s in before["silent_sites"]}   # pas encore muettes


def test_evening_view_rejects_out_of_range(fake_warehouse):
    assert client(fake_warehouse).get("/evening/2022-02-01").status_code == 422


def test_ask_returns_structured_answer_and_steps(fake_warehouse):
    r = client(fake_warehouse).post("/ask", json={"question": "Quelle borne est en tete ?", "evening": "2021-10-05"})
    d = r.json()
    assert r.status_code == 200 and d["answer"]["status"] == "answered"
    assert d["answer"]["text"].startswith("Borne 23") and d["steps"][0]["tool"] == "get_evening_list"
    assert d["model"] == "flash_lite" and not d["fallback_used"]


def test_fallback_when_champion_quota_is_exhausted(fake_warehouse):
    factory = lambda name: DownLLM() if name == "flash_lite" else FakeLLM()
    d = client(fake_warehouse, factory).post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"}).json()
    assert d["fallback_used"] and d["model"] == "gpt_oss" and d["answer"]["status"] == "answered"


def test_503_when_both_llms_are_down(fake_warehouse):
    r = client(fake_warehouse, lambda name: DownLLM()).post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})
    assert r.status_code == 503


@pytest.mark.parametrize("payload", [
    {"question": "Liste ?", "evening": "2022-01-15"},        # apres le rejeu
    {"question": "Liste ?", "evening": "2021-06-01"},        # avant le rejeu
    {"question": "", "evening": "2021-10-05"},
    {"question": "x" * 301, "evening": "2021-10-05"},
])
def test_invalid_requests_are_rejected(fake_warehouse, payload):
    assert client(fake_warehouse).post("/ask", json=payload).status_code == 422


def test_daily_limit_of_the_demo(fake_warehouse):
    c = client(fake_warehouse, max_questions_per_day=1)
    ok = c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})
    over = c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})
    assert ok.status_code == 200 and over.status_code == 429


def _norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def test_suggested_questions_never_reproduce_a_test_question():
    items = yaml.safe_load((PROJECT_ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))
    items = items["questions"] if isinstance(items, dict) else items
    test_q = {_norm(i["question"]) for i in items if i["split"] == "test"}
    sites = ["Wholesale Market", "Shopping Mall", "Bus Station", "Park A", "Park B", "Tourist Attraction",
             "Expressway Service District B", "Expressway Service District C", "Government Agency",
             "Technology Park", "Industrial Park", "Wholesale Market"]
    for q in all_rendered(sites, list(range(1, 93))):
        assert "{" not in q
        assert _norm(q) not in test_q, q


def test_slow_champion_hands_over_to_the_fallback(fake_warehouse):
    # budget negatif : le champion est juge "trop lent" des le premier appel
    c = client(fake_warehouse, champion_budget_s=-1)
    d = c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"}).json()
    assert d["fallback_used"] and d["model"] == "gpt_oss" and "trop lent" in d["notes"][0]
    assert d["answer"]["status"] == "answered" and d["llm_latencies_s"]


def test_champion_within_budget_keeps_the_question(fake_warehouse):
    d = client(fake_warehouse, champion_budget_s=60).post(
        "/ask", json={"question": "Liste ?", "evening": "2021-10-05"}).json()
    assert d["model"] == "flash_lite" and not d["notes"]


def test_exhausted_model_is_not_called_again_the_same_day(fake_warehouse):
    calls = {"flash_lite": 0}

    class CountingDown(DownLLM):
        def chat(self, *a, **k):
            calls["flash_lite"] += 1
            return super().chat(*a, **k)
    factory = lambda name: CountingDown() if name == "flash_lite" else FakeLLM()
    c = client(fake_warehouse, factory)
    for _ in range(2):
        d = c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"}).json()
        assert d["model"] == "gpt_oss"
    assert calls["flash_lite"] == 1          # le 2e appel ne retente pas un quota epuise


def test_unavailable_message_is_plain_french(fake_warehouse):
    r = client(fake_warehouse, lambda name: DownLLM()).post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})
    assert r.status_code == 503 and "Réessayez" in r.json()["detail"] and "Error code" not in r.json()["detail"]


def test_prepared_answer_is_instant_and_outside_the_quota(fake_warehouse, tmp_path):
    from datetime import date
    from api.prepared import PreparedStore
    store = PreparedStore(tmp_path / "prepared.json")
    store.put(date(2021, 10, 5), "Pourquoi la borne 23 est-elle dans la liste ce soir ?",
              {"answer": {"status": "answered", "text": "prepare", "figures": [], "sources": ["get_post_signals"]},
               "steps": [{"tool": "get_post_signals", "ok": True}], "model": "flash_lite",
               "prepared_at": "2026-10-21T10:00+02:00"})
    store.save()
    c = TestClient(create_app(Desk(fake_warehouse, lambda n: DownLLM(), max_questions_per_day=0,
                                   prepared=PreparedStore(tmp_path / "prepared.json"))))
    # LLM indisponibles et quota a zero : la reponse preparee passe quand meme, ponctuation et casse ignorees
    d = c.post("/ask", json={"question": "pourquoi la borne 23 est-elle dans la liste ce soir",
                             "evening": "2021-10-05"}).json()
    assert d["prepared"] and d["answer"]["text"] == "prepare"
    assert c.get("/meta").json()["prepared_evenings"] == ["2021-10-05"]
    # un autre soir n'est pas prepare : on retombe sur le direct (ici, limite atteinte)
    assert c.post("/ask", json={"question": "Pourquoi la borne 23 est-elle dans la liste ce soir ?",
                                "evening": "2021-10-06"}).status_code == 429


def test_prepare_asks_exactly_the_questions_of_the_page(fake_warehouse):
    from datetime import date
    from api.prepare import questions_for
    from api.service import evening_overview
    qs = questions_for(evening_overview(fake_warehouse, date(2021, 10, 5)))
    assert len(qs) == 10 + 2 + len(FREQUENT)          # 10 bornes, 2 sites muets hors liste, questions utiles
    assert qs[0] == "Pourquoi la borne 23 est-elle dans la liste ce soir ?"


def test_prepare_runs_end_to_end_with_a_fake_llm(fake_warehouse, tmp_path, monkeypatch):
    import api.prepare as prep
    monkeypatch.setattr(prep, "load_config", lambda: {})
    monkeypatch.setattr(prep, "warehouse_path", lambda cfg: fake_warehouse)
    monkeypatch.setattr(prep, "data_dir", lambda cfg: tmp_path)
    monkeypatch.setattr(prep.LLMClient, "from_config", classmethod(lambda cls, name: FakeLLM()))
    prep.main(["--only", "2021-10-05"])
    from api.prepared import PreparedStore
    store = PreparedStore(tmp_path / "demo" / "prepared.json")
    assert len(store.items) == 16 and (tmp_path / "demo" / "prepared_report.md").exists()
    prep.main(["--only", "2021-10-05"])              # relance : rien a refaire
    assert len(PreparedStore(tmp_path / "demo" / "prepared.json").items) == 16


def test_missing_api_keys_give_a_clear_503_and_prepared_answers_still_work(fake_warehouse):
    def no_key(name):
        raise RuntimeError("cle GEMINI_API_KEY absente du fichier .env")
    c = client(fake_warehouse, no_key)
    assert c.get("/health").status_code == 200
    r = c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})
    assert r.status_code == 503 and "configuré" in r.json()["detail"]


def test_server_without_api_keys_answers_503_not_500(fake_warehouse):
    def no_key(name):
        raise RuntimeError("cle GEMINI_API_KEY absente du fichier .env")
    r = client(fake_warehouse, no_key).post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})
    assert r.status_code == 503 and "configuré" in r.json()["detail"]


def test_every_question_is_journaled_and_counted(fake_warehouse, tmp_path):
    from datetime import date
    from api.journal import Journal
    from api.prepared import PreparedStore
    store = PreparedStore(tmp_path / "p.json")
    store.put(date(2021, 10, 5), "Question préparée ?", {"answer": {"status": "answered", "text": "ok", "figures": []},
                                                        "steps": [], "model": "flash_lite"})
    j = Journal(tmp_path / "monitoring" / "questions.jsonl")
    factory = lambda name: DownLLM() if name == "flash_lite" else FakeLLM()
    c = TestClient(create_app(Desk(fake_warehouse, factory, max_questions_per_day=2, prepared=store), journal=j))
    c.post("/ask", json={"question": "Question préparée ?", "evening": "2021-10-05"})      # preparee
    c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"})                  # direct, repli
    c.post("/ask", json={"question": "Encore ?", "evening": "2021-10-05"})                 # direct
    c.post("/ask", json={"question": "Trop ?", "evening": "2021-10-05"})                   # limite : 429
    lines = [json.loads(l) for l in (tmp_path / "monitoring" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [l["source"] for l in lines] == ["preparee", "direct", "direct", "refusee"]
    assert lines[1]["fallback_used"] and lines[1]["model"] == "gpt_oss" and lines[1]["tools"] == ["get_evening_list"]
    assert lines[3]["http"] == 429 and "ip" not in json.dumps(lines).lower()
    s = c.get("/stats").json()
    assert s["questions"] == 4 and s["prepared"] == 1 and s["fallback"] == 2 and s["daily_limit"] == 1


def test_unavailable_is_journaled_with_its_cause(fake_warehouse, tmp_path):
    from api.journal import Journal
    from api.report_monitoring import load, summarize
    path = tmp_path / "q.jsonl"
    c = TestClient(create_app(Desk(fake_warehouse, lambda n: DownLLM()), journal=Journal(path)))
    assert c.post("/ask", json={"question": "Liste ?", "evening": "2021-10-05"}).status_code == 503
    s = summarize(load(path))
    assert s["echecs_direct"] == 1 and s["causes_echec"]["quota épuisé"] == 1


def test_monitoring_report_reads_render_log_lines(tmp_path):
    from api.report_monitoring import load, summarize, to_markdown
    rows = [{"ts": f"2026-10-22T{h:02d}:00:00+00:00", "source": "direct", "http": 200, "status": "answered",
             "latency_s": lat, "tokens": 5000, "tools": ["get_post_signals"], "model": "flash_lite",
             "fallback_used": False, "notes": []} for h, lat in [(8, 3.0), (8, 5.0), (15, 30.0)]]
    rows.append({"ts": "2026-10-22T15:05:00+00:00", "source": "preparee", "http": 200, "status": "answered",
                 "latency_s": 0.0, "tools": []})
    text = "\n".join("INFO:chargedesk.journal:question " + json.dumps(r) for r in rows) + "\nbruit sans json\n"
    (tmp_path / "render.log").write_text(text, encoding="utf-8")
    s = summarize(load(tmp_path / "render.log"))
    assert s["questions"] == 4 and s["preparees"] == 1 and s["latence_direct_mediane_s"] == 5.0
    assert s["latence_par_heure_utc"] == {8: 4.0, 15: 30.0}
    assert "rapport de surveillance" in to_markdown(s)
