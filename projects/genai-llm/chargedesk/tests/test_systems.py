import json
from datetime import date

from chargedesk.eval.grading import grade
from chargedesk.eval.schema import Answer, Expected, Figure
from chargedesk.eval.run import guard_test_opening
from chargedesk.llm.client import LLMResponse
from chargedesk.systems import no_tools, text_to_sql

E = date(2021, 10, 5)


class ScriptedLLM:
    """Faux LLM : renvoie les textes prevus, dans l'ordre, et garde les messages recus."""
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def chat(self, messages, tools=None, rep=0):
        self.seen.append(messages)
        return LLMResponse(content=self.replies.pop(0), tool_calls=[], prompt_tokens=100,
                           completion_tokens=20, latency_s=0.1, cached=False, model="fake")


def answer(value, sources=("run_sql",)):
    return json.dumps({"status": "answered", "text": f"{value} pannes", "sources": list(sources),
                       "figures": [{"name": "pannes", "value": value, "unit": "count"}]})


def test_no_tools_invented_figure_is_not_supported(fake_warehouse):
    llm = ScriptedLLM([answer(190, sources=("memoire",))])
    out = no_tools.run(llm, fake_warehouse, E, "Combien de pannes ?")
    g = grade(Answer(**out["answer"]), Expected(status="answered",
              figures=[Figure(name="p", value=190, unit="count")]), out["tool_results"])
    assert g.correct and g.unsupported == ["pannes"]   # juste par hasard, mais invente


def test_text_to_sql_answer_is_supported_by_query_rows(fake_warehouse):
    from chargedesk.data.snapshot import snapshot_connection
    con = snapshot_connection(fake_warehouse, E)
    truth = con.execute("select sum(n_hw_faults) from marts.fct_post_day where site = 'Shopping Mall' "
                        "and day between date '2021-09-29' and date '2021-10-05'").fetchone()[0]
    con.close()
    sql = json.dumps({"action": "sql", "sql": "select sum(n_hw_faults) as pannes from marts.fct_post_day "
                      "where site = 'Shopping Mall' and day between date '2021-09-29' and date '2021-10-05'"})
    llm = ScriptedLLM([sql, answer(truth)])
    out = text_to_sql.run(llm, fake_warehouse, E, "Pannes du Shopping Mall sur 7 jours ?")
    g = grade(Answer(**out["answer"]), Expected(status="answered",
              figures=[Figure(name="p", value=truth, unit="count")]), out["tool_results"])
    assert g.correct and g.unsupported == []
    assert "marts.fct_post_evening" in llm.seen[0][0]["content"]       # schema donne au LLM
    assert "fct_post_signals" not in llm.seen[0][0]["content"]         # table interdite absente


def test_text_to_sql_gets_one_chance_to_fix_a_rejected_query(fake_warehouse):
    bad = json.dumps({"action": "sql", "sql": "delete from marts.fct_post_day"})
    good = json.dumps({"action": "sql", "sql": "select count(*) as n from marts.dim_post"})
    llm = ScriptedLLM([bad, good, answer(1)])
    out = text_to_sql.run(llm, fake_warehouse, E, "Combien de bornes ?")
    assert len(out["sql_errors"]) == 1 and "lecture" in out["sql_errors"][0]
    assert out["tool_results"] and "Erreur" in llm.seen[1][-1]["content"]


def test_text_to_sql_never_sees_the_future(fake_warehouse):
    sql = json.dumps({"action": "sql", "sql": "select max(day) as d from marts.fct_post_day"})
    llm = ScriptedLLM([sql, answer(1)])
    out = text_to_sql.run(llm, fake_warehouse, E, "Dernier jour connu ?")
    assert out["tool_results"][0][0]["d"] == "2021-10-05"


def test_text_to_sql_refusal_is_structured(fake_warehouse):
    llm = ScriptedLLM([json.dumps({"action": "refuse", "refusal_reason": "causal", "text": "pas de cause"})])
    out = text_to_sql.run(llm, fake_warehouse, E, "Pourquoi ?")
    assert out["answer"]["status"] == "refuse" and out["answer"]["refusal_reason"] == "causal"


def test_unreadable_output_is_recorded_not_crashing(fake_warehouse):
    out = no_tools.run(ScriptedLLM(["je ne sais pas"]), fake_warehouse, E, "?")
    assert out["answer"] is None and "invalide" in out["error"]


def test_test_set_opens_only_once(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        guard_test_opening("no_tools", "m", confirmed=False, folder=tmp_path)
    guard_test_opening("no_tools", "m", confirmed=True, folder=tmp_path)
    (tmp_path / "no_tools__m__test.jsonl").write_text(json.dumps({"meta": {"complete": True}}) + "\n",
                                                      encoding="utf-8")
    with pytest.raises(SystemExit, match="deja ouvert"):
        guard_test_opening("no_tools", "m", confirmed=True, folder=tmp_path)


def test_run_one_grades_and_measures(fake_warehouse):
    from chargedesk.eval.run import run_one
    from chargedesk.eval.report import summarize
    item = {"id": "dev-31", "category": "modification", "evening": "2021-10-05",
            "question": "Retire la borne 23 de la liste.",
            "expected": {"status": "refuse", "figures": [], "refusal_reason": "modification"}}
    llm = ScriptedLLM([json.dumps({"status": "refuse", "text": "Lecture seule.",
                                   "refusal_reason": "modification"})])
    row = run_one(no_tools, llm, fake_warehouse, item, rep=0)
    assert row["grade"]["correct"] and row["n_calls"] == 1 and row["tokens"] == 120
    s = summarize([row])
    assert s["refus_corrects"] == 1.0 and s["exactitude"] == 1.0


def test_technical_error_is_not_counted_as_wrong(fake_warehouse):
    from chargedesk.eval.report import summarize
    from chargedesk.eval.run import run_one
    from chargedesk.llm.client import TransientError

    class DeadLLM:
        def chat(self, *a, **k):
            raise TransientError("pas de reponse")
    item = {"id": "dev-01", "category": "fact", "evening": "2021-10-05", "question": "?",
            "expected": {"status": "answered", "figures": [{"name": "p", "value": 1, "unit": "count"}],
                         "refusal_reason": None}}
    row = run_one(no_tools, DeadLLM(), fake_warehouse, item, rep=0)
    assert row["infra_error"]
    s = summarize([row])
    assert s["n"] == 0 and s["erreurs_techniques"] == 1.0


def test_interrupted_test_run_can_resume_but_finished_one_cannot(tmp_path):
    import pytest
    guard_test_opening("agent", "m", True, tmp_path)               # premiere ouverture
    out = tmp_path / "agent__m__test.jsonl"
    out.write_text(json.dumps({"meta": {"complete": False}}) + "\n", encoding="utf-8")
    guard_test_opening("agent", "m", True, tmp_path)               # interrompue : reprise permise
    out.write_text(json.dumps({"meta": {"complete": True}}) + "\n"
                   + json.dumps({"id": "t1", "infra_error": False}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        guard_test_opening("agent", "m", True, tmp_path)           # terminee : refus
