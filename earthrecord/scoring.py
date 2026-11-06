"""Scoring of EarthRecord answers.

Each question has a reference: its answer fields with reference values, numeric ranges and accepted alternatives, and the
name of its conclusion field. A run is *right* when its conclusion field earns full credit; where a conclusion is decided
by the sign of a number, that number must also lie inside its reference range. A question is solved by a model when the
run is right in all three passes (pass^3).

Field scores (0 to 1):
- choice: exact match with the reference or an accepted alternative;
- year: exact match, or 0.5 when one year off; month: the same with months wrapping around the year;
- set of years: F1 score, a year counting as matched when it is within one year of a reference year;
- number: 1 inside the reference range (plus an absolute tolerance); outside it, mean relative accuracy on the distance to
  the nearest bound (thresholds 0.50 to 0.95);
- "insufficient_evidence" earns 1 only where it is the reference.

The question score gives the conclusion half of the weight and shares the other half among the remaining fields; a wrong
conclusion sets the question score to 0. It is reported for completeness; the paper's results use right and pass^3.
"""

import math

INSUFFICIENT_EVIDENCE = "insufficient_evidence"
OPPOSITES = {("increase", "decrease"), ("advanced", "retreated"), ("later", "earlier"), ("longer", "shorter"),
             ("snowier", "less_snowy"), ("increased", "decreased"), ("yes", "no")}


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and not (
        isinstance(value, float) and math.isnan(value))


def _mean_relative_accuracy(relative_error: float) -> float:
    return sum(1 for k in range(10) if relative_error < 1 - (0.5 + 0.05 * k)) / 10.0


def score_field(spec: dict, value) -> float:
    """Score one answer field against its reference specification."""
    reference = spec.get("reference")
    if reference == INSUFFICIENT_EVIDENCE:
        return 1.0 if value == INSUFFICIENT_EVIDENCE else 0.0
    if value == INSUFFICIENT_EVIDENCE or value is None:
        return 0.0
    kind = spec["kind"]
    if kind in ("year", "month"):
        try:
            v = int(value)
        except (TypeError, ValueError):
            return 0.0
        accepted = spec.get("accept") or ([int(reference)] if _is_number(reference) else [])
        if v in accepted:
            return 1.0
        if kind == "month":
            return 0.5 if any(min(abs(v - a), 12 - abs(v - a)) == 1 for a in accepted) else 0.0
        return 0.5 if any(abs(v - a) == 1 for a in accepted) else 0.0
    if kind == "choice":
        accepted = [str(a).strip().lower() for a in spec.get("accept") or [reference]]
        return 1.0 if str(value).strip().lower() in accepted else 0.0
    if kind == "set":
        if not isinstance(value, list) or not isinstance(reference, list):
            return 0.0
        predicted = [int(x) for x in value if _is_number(x)]
        gold = [int(x) for x in reference]
        if not predicted and not gold:
            return 1.0
        if not predicted or not gold:
            return 0.0
        hits_predicted = sum(1 for p in predicted if any(abs(p - g) <= 1 for g in gold))
        hits_gold = sum(1 for g in gold if any(abs(p - g) <= 1 for p in predicted))
        precision, recall = hits_predicted / len(predicted), hits_gold / len(gold)
        return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    if kind == "num":
        if not _is_number(value) or not _is_number(reference):
            return 0.0
        low, high = spec["range"] if spec.get("range") else (reference, reference)
        tolerance = spec.get("abs_tol") or 0.0
        if low - tolerance <= value <= high + tolerance:
            return 1.0
        distance = (low - tolerance - value) if value < low else (value - high - tolerance)
        return _mean_relative_accuracy(distance / max(abs(reference), 10 * tolerance, 1e-9))
    return 0.0


def _field_for_year(spec: dict, answer: dict) -> dict:
    """A field that depends on the year the answer picked is judged against the reference of that year."""
    by_year, year = spec.get("by_year"), answer.get(spec.get("depends_on"))
    if not by_year or not _is_number(year) or str(int(year)) not in by_year:
        return spec
    value = by_year[str(int(year))]
    if spec["kind"] != "num":
        return dict(spec, reference=value)
    year_range = (spec.get("by_year_range") or {}).get(str(int(year))) or [value - 3.0, value + 3.0]
    return dict(spec, reference=value, range=year_range)


def _sign(x: float, tolerance: float) -> int:
    return 0 if abs(x) <= tolerance else (1 if x > 0 else -1)


def score_conclusion(reference: dict, answer: dict) -> tuple:
    """Score the conclusion. Returns (score, answered value, reference value, abstained, reversed)."""
    conclusion = reference["conclusion"]
    fields = {f["name"]: f for f in reference["fields"]}
    if isinstance(conclusion, str):
        spec = fields[conclusion]
        value, ref = answer.get(conclusion), spec.get("reference")
        reversed_ = isinstance(value, str) and isinstance(ref, str) and (
            (value, ref) in OPPOSITES or (ref, value) in OPPOSITES)
        abstained = value == INSUFFICIENT_EVIDENCE and ref != INSUFFICIENT_EVIDENCE
        return score_field(spec, value), value, ref, abstained, reversed_
    rule = conclusion[0]
    if rule == "recovered":
        spec = fields[conclusion[1]]
        value, ref = answer.get(conclusion[1]), spec.get("reference")
        if value == INSUFFICIENT_EVIDENCE:
            return 0.0, value, ref, True, False
        answered = "recovered" if _is_number(value) else "not_recovered"
        expected = "recovered" if _is_number(ref) else "not_recovered"
        return (1.0 if answered == expected else 0.0), answered, expected, False, answered != expected
    if rule in ("sign", "sign_ratio"):
        spec = fields[conclusion[1]]
        value, ref = answer.get(conclusion[1]), spec.get("reference")
        tolerance = 0.05 if rule == "sign_ratio" else (spec.get("abs_tol") or 0.0)
        if value == INSUFFICIENT_EVIDENCE or not _is_number(value):
            return 0.0, value, ref, value == INSUFFICIENT_EVIDENCE, False
        offset = 1.0 if rule == "sign_ratio" else 0.0
        a, b = _sign(value - offset, tolerance), _sign(ref - offset, tolerance)
        score = 1.0 if a == b or a in reference.get("sign_accept", ()) else 0.0
        return score, a, b, False, a * b == -1
    if rule == "sign_diff":
        first, second = fields[conclusion[1]], fields[conclusion[2]]
        v1, v2 = answer.get(conclusion[1]), answer.get(conclusion[2])
        if not (_is_number(v1) and _is_number(v2)):
            return 0.0, None, None, v1 == INSUFFICIENT_EVIDENCE or v2 == INSUFFICIENT_EVIDENCE, False
        tolerance = max(first.get("abs_tol") or 0.0, second.get("abs_tol") or 0.0)
        a = _sign(v1 - v2, tolerance)
        b = _sign(first["reference"] - second["reference"], tolerance)
        score = 1.0 if a == b or a in reference.get("sign_accept", ()) else 0.0
        return score, a, b, False, a * b == -1
    raise ValueError("unknown conclusion rule: %r" % (conclusion,))


def is_right(reference: dict, answer: dict | None) -> bool:
    """The conclusion at full credit; a number that decides the conclusion by its sign must also be in its range."""
    answer = answer or {}
    conclusion = reference["conclusion"]
    if score_conclusion(reference, answer)[0] < 1:
        return False
    if isinstance(conclusion, str) or conclusion[0] == "recovered":
        return True
    fields = {f["name"]: f for f in reference["fields"]}
    return all(score_field(fields[name], answer.get(name)) == 1.0 for name in conclusion[1:])


def score_run(reference: dict, answer: dict | None) -> dict:
    """Score one run: right, abstained, question score, per-field scores and the reported confidence (0 to 1)."""
    answer = answer if isinstance(answer, dict) else {}
    conclusion_score, _, _, abstained, _ = score_conclusion(reference, answer)
    conclusion_field = reference["conclusion"] if isinstance(reference["conclusion"], str) else None
    scored = [f for f in reference["fields"] if f["kind"] != "ci"]
    field_scores = {f["name"]: score_field(_field_for_year(f, answer), answer.get(f["name"])) for f in scored}
    # a field whose reference is null does not apply under the reference conclusion and is not scored
    others = [f for f in scored if f["name"] != conclusion_field and f.get("reference") is not None]
    if not others:
        question_score = conclusion_score
    elif conclusion_score == 0:
        question_score = 0.0
    else:
        question_score = 0.5 * conclusion_score + 0.5 * sum(field_scores[f["name"]] for f in others) / len(others)
    reference_insufficient = all(f.get("reference") == INSUFFICIENT_EVIDENCE for f in scored)
    confidence = answer.get("confidence")
    return {
        "right": is_right(reference, answer),
        "abstained": bool(abstained) and not reference_insufficient,
        "question_score": question_score,
        "conclusion_score": conclusion_score,
        "field_scores": field_scores,
        "confidence": confidence / 100.0 if _is_number(confidence) else None,
    }


def pass_k(rights: list[bool]) -> bool:
    """pass^k: right in every pass."""
    return bool(rights) and all(rights)
