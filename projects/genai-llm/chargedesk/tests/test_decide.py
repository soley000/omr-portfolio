from chargedesk.eval.decide import bootstrap_gain, decide


def row(q, ok, rep=0, status="answered", lat=1.0, infra=False):
    if q == "q0":   # une question a refuser dans chaque jeu
        status = "refuse"
    return {"id": q, "rep": rep, "category": "fact", "expected_status": status, "infra_error": infra,
            "answer": {"status": status, "figures": []}, "sql": [], "sql_errors": [],
            "grade": {"correct": ok, "unsupported": []}, "latency_s": lat, "tokens": 10}


def test_clear_gain_passes_and_slow_candidate_fails():
    base = [row(f"q{i}", i < 14) for i in range(20)]          # 70 %
    fast = [row(f"q{i}", True) for i in range(20)]             # 100 %
    slow = [row(f"q{i}", True, lat=30) for i in range(20)]
    assert decide(fast, base)["verdict"]
    res = decide(slow, base)
    assert not res["verdict"]
    assert [ok for ok, _ in res["checks"].values()] == [True, True, True, False]


def test_no_gain_has_interval_around_zero():
    a = [row(f"q{i}", i % 2 == 0) for i in range(30)]
    gain, lo, hi = bootstrap_gain({r["id"]: float(r["grade"]["correct"]) for r in a},
                                  {r["id"]: float(r["grade"]["correct"]) for r in a})
    assert gain == 0 and lo <= 0 <= hi


def test_technical_errors_are_left_out():
    base = [row("q1", False)]
    cand = [row("q1", True), row("q1", False, rep=1, infra=True)]
    gain, _, _ = bootstrap_gain({"q1": 1.0}, {"q1": 0.0})
    assert gain == 1.0
    from chargedesk.eval.decide import per_question
    assert per_question(cand) == {"q1": 1.0}
