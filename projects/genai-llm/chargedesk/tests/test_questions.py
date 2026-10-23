from chargedesk.config import load_config
from chargedesk.eval.build_expected import build
from chargedesk.eval.questions import check_plan, load_questions


def test_question_file_is_valid_and_follows_plan():
    questions = load_questions()
    assert len(questions) == 62
    assert check_plan(questions, load_config()["evaluation"]) == []


def test_every_gold_query_runs_without_leak(fake_warehouse):
    items = build(load_questions(), fake_warehouse)
    assert len(items) == 62
    answered = [i for i in items if i["expected"]["status"] == "answered"]
    assert all(i["expected"]["figures"] for i in answered)


def test_a_question_that_needs_the_future_is_rejected(fake_warehouse):
    import pytest
    from chargedesk.eval.build_expected import GoldError
    from chargedesk.eval.questions import Question

    leaky = Question(
        id="dev-99", split="dev", evening="2021-10-05", category="fact",
        question="Combien de pannes au Shopping Mall ?", expected_status="answered",
        figures=[{"name": "toutes les pannes", "unit": "count",
                  "sql": "select sum(n_hw_faults) as value from marts.fct_post_day where site = 'Shopping Mall'"}],
    )
    with pytest.raises(GoldError, match="fuite"):
        build([leaky], fake_warehouse)


def test_all_problems_are_collected_not_just_the_first(fake_warehouse):
    from chargedesk.eval.questions import Question

    def bad(i):
        return Question(id=f"dev-9{i}", split="dev", evening="2021-10-05", category="fact",
                        question="Question sans reponse", expected_status="answered",
                        figures=[{"name": "vide", "unit": "count",
                                  "sql": "select null as value"}])
    errors = []
    items = build([bad(1), bad(2)], fake_warehouse, errors)
    assert items == [] and len(errors) == 2
