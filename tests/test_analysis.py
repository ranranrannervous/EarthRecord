from earthrecord.analysis import Results, always_no_change, majority_class

REFERENCES = {
    "q1": {"id": "q1", "conclusion": "direction", "fields": [{"name": "direction", "kind": "choice", "reference": "decrease"}]},
    "q2": {"id": "q2", "conclusion": "direction", "fields": [{"name": "direction", "kind": "choice", "reference": "decrease"}]},
    "q3": {"id": "q3", "conclusion": "direction",
           "fields": [{"name": "direction", "kind": "choice", "reference": "no_significant_change"}]},
}
FIELDS = [{"name": "direction", "kind": "choice", "options": ["increase", "decrease", "no_significant_change"]}]


def question(qid, version="original", no_change=False):
    return {"id": qid, "version": version, "pair": qid, "fields": FIELDS, "class": "computable",
            "no_change_reference": no_change, "alteration": {"type": "Terra NDVI"} if version != "original" else None}


QUESTIONS = [question("q1"), question("q2"), question("q3", no_change=True), question("q1", "altered"),
             question("q3", "altered")]


def runs(setting, version, qid, answers):
    return [{"model": "m", "setting": setting, "version": version, "question": qid, "pass": i + 1,
             "answer": {"direction": a, "confidence": 80}} for i, a in enumerate(answers)]


def test_pass3_and_pair_cases():
    data = (runs("record", "original", "q1", ["decrease"] * 3) + runs("record", "altered", "q1", ["decrease", "increase", "decrease"])
            + runs("record", "original", "q2", ["decrease", "decrease", "increase"])
            + runs("record", "original", "q3", ["no_significant_change"] * 3)
            + runs("record", "altered", "q3", ["no_significant_change"] * 3)
            + runs("closed_book", "original", "q1", ["increase"] * 3))
    res = Results(data, QUESTIONS, REFERENCES)
    assert res.pass3("m", "q1") and not res.pass3("m", "q2")
    assert res.pair_case("m", "q1") == "moved"          # right on the original, not on the altered version
    assert res.pair_case("m", "q3") == "held"           # stays right, and no change is the reference
    assert res.pair_case("m", "q2") == "wrong_on_original"


def test_baselines():
    questions = {q["id"]: q for q in QUESTIONS if q["version"] == "original"}
    majority = majority_class(questions, REFERENCES)
    # leave one out: q1 and q2 see a tie, which goes to the class met first in reference order (decrease); q3 sees decrease
    assert majority == {"q1": True, "q2": True, "q3": False}
    assert always_no_change(questions, REFERENCES) == {"q1": False, "q2": False, "q3": True}
