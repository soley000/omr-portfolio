import pytest
from pydantic import ValidationError

from chargedesk.eval.grading import grade, numbers_in
from chargedesk.eval.schema import Answer, Expected, Figure

TOOL = [{"site": "Shopping Mall", "n_hw_faults": 11037, "hw_fault_rate": 0.1950}]
EXPECTED = Expected(status="answered", figures=[Figure(name="pannes", value=11037, unit="count")])


def _answer(value, unit="count", **kw):
    return Answer(status="answered", text="ok",
                  figures=[Figure(name="pannes", value=value, unit=unit)],
                  sources=["get_metric"], **kw)


def test_exact_count_is_correct_and_supported():
    g = grade(_answer(11037), EXPECTED, TOOL)
    assert g.correct and g.unsupported == []


def test_count_must_be_exact():
    assert not grade(_answer(11036), EXPECTED, TOOL).correct


def test_rate_tolerance_is_one_tenth_of_a_point():
    exp = Expected(status="answered", figures=[Figure(name="taux", value=0.1950, unit="rate")])
    assert grade(_answer(0.1955, "rate"), exp, TOOL).correct      # 0,05 point d'ecart
    assert not grade(_answer(0.1970, "rate"), exp, TOOL).correct  # 0,2 point d'ecart


def test_score_rounded_to_two_decimals_is_accepted():
    exp = Expected(status="answered", figures=[Figure(name="score borne 23", value=0.356, unit="score")])
    ans = Answer(status="answered", text="0,36", figures=[Figure(name="score", value=0.36, unit="score")],
                 sources=["get_ranking"])
    assert grade(ans, exp, [{"post_id": 23, "score": 0.356}]).correct


def test_invented_figure_is_flagged_unsupported():
    ans = Answer(status="answered", text="ok", sources=["get_metric"],
                 figures=[Figure(name="pannes", value=11037, unit="count"),
                          Figure(name="hausse", value=42, unit="count")])
    g = grade(ans, EXPECTED, TOOL)
    assert g.correct and g.unsupported == ["hausse"]


def test_refusal_needs_the_right_reason():
    exp = Expected(status="refuse", refusal_reason="causal")
    good = Answer(status="refuse", text="Les donnees ne permettent pas d'etablir une cause.", refusal_reason="causal")
    wrong = Answer(status="refuse", text="Pas de donnees.", refusal_reason="out_of_data")
    assert grade(good, exp, []).correct
    assert not grade(wrong, exp, []).correct


def test_answering_instead_of_clarifying_is_wrong():
    exp = Expected(status="clarify")
    assert not grade(_answer(11037), exp, TOOL).correct


def test_schema_rejects_incoherent_answers():
    with pytest.raises(ValidationError):
        Answer(status="refuse", text="non")                      # refus sans raison
    with pytest.raises(ValidationError):
        Answer(status="answered", text="11 037",
               figures=[Figure(name="pannes", value=11037, unit="count")])  # chiffre sans source
    with pytest.raises(ValidationError):
        Figure(name="pannes", value=3, unit="euros")             # unite inconnue


def test_numbers_in_ignores_booleans_and_nan():
    assert numbers_in({"a": [1, {"b": 2.5}], "ok": True, "x": float("nan"), "s": "23"}) == [1.0, 2.5]