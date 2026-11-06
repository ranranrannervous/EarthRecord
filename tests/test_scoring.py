from earthrecord.scoring import INSUFFICIENT_EVIDENCE, is_right, pass_k, score_field, score_run

TREND = {
    "id": "example-trend",
    "conclusion": "direction",
    "fields": [
        {"name": "direction", "kind": "choice", "reference": "decrease"},
        {"name": "rate", "kind": "num", "reference": -0.05, "range": [-0.06, -0.04], "abs_tol": 0.0},
    ],
}
SIGN = {
    "id": "example-sign",
    "conclusion": ["sign", "change_km2"],
    "fields": [{"name": "change_km2", "kind": "num", "reference": 12.0, "range": [10.0, 14.0], "abs_tol": 0.5}],
}
INSUFFICIENT = {
    "id": "example-insufficient",
    "conclusion": "change_km2",
    "fields": [{"name": "change_km2", "kind": "num", "reference": INSUFFICIENT_EVIDENCE}],
}


def test_choice_conclusion():
    assert is_right(TREND, {"direction": "decrease", "rate": -0.2})
    assert not is_right(TREND, {"direction": "increase", "rate": -0.05})


def test_question_score_shares_the_other_fields():
    assert score_run(TREND, {"direction": "decrease", "rate": -0.05})["question_score"] == 1.0
    assert score_run(TREND, {"direction": "decrease", "rate": 1.0})["question_score"] == 0.5
    assert score_run(TREND, {"direction": "increase", "rate": -0.05})["question_score"] == 0.0


def test_sign_conclusion_needs_the_number_in_range():
    assert is_right(SIGN, {"change_km2": 13.0})
    assert not is_right(SIGN, {"change_km2": 30.0})  # right sign, outside the range
    assert not is_right(SIGN, {"change_km2": -13.0})


def test_years_and_months():
    year = {"kind": "year", "reference": 2011, "accept": [2011]}
    assert score_field(year, 2011) == 1.0 and score_field(year, 2012) == 0.5 and score_field(year, 2014) == 0.0
    month = {"kind": "month", "reference": 12, "accept": [12]}
    assert score_field(month, 1) == 0.5


def test_numbers_outside_the_range_get_partial_credit():
    spec = {"kind": "num", "reference": 100.0, "range": [95.0, 105.0], "abs_tol": 0.0}
    assert score_field(spec, 100.0) == 1.0
    assert 0.0 < score_field(spec, 120.0) < 1.0
    assert score_field(spec, 1000.0) == 0.0


def test_insufficient_evidence():
    assert is_right(INSUFFICIENT, {"change_km2": INSUFFICIENT_EVIDENCE})
    assert not is_right(INSUFFICIENT, {"change_km2": 3.0})
    run = score_run(TREND, {"direction": INSUFFICIENT_EVIDENCE, "rate": INSUFFICIENT_EVIDENCE})
    assert run["abstained"] and not run["right"]
    assert not score_run(INSUFFICIENT, {"change_km2": INSUFFICIENT_EVIDENCE})["abstained"]


def test_pass_k():
    assert pass_k([True, True, True])
    assert not pass_k([True, False, True])
    assert not pass_k([])
