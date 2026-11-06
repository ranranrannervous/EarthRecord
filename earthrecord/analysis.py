"""The paper's results from per-run results: pass^3 tables, the two baselines and the instrument-pair outcomes.

Definitions (see the paper, Sections 2-4):
- a run is right when its conclusion field earns full credit (earthrecord.scoring.is_right);
- pass^3: right in all three passes; scores are percentages of questions;
- the main results use the 226 computable and recognition questions with the record;
- a model-pair case is right on the original when the original question is right in all three passes with the record. It
  *moves* when the altered version is not; it is *held* when it stays right and is right in the closed book or has no
  change as the reference; otherwise it holds *beyond* both;
- baselines: the majority class (leave one out: the most common reference conclusion among the other questions with the
  same answer type; numeric conclusions have no class) and always answering no change where the conclusion offers it.
"""

import collections
import gzip
import json
import random
import statistics
from pathlib import Path

from .scoring import INSUFFICIENT_EVIDENCE, is_right, score_run

NO_CHANGE = ("no_significant_change", "no", "stable", "about_the_same")
BOOTSTRAP_SEED, BOOTSTRAP_SAMPLES = 20261102, 2000
DIRECTION_ORDER = {"decrease": -1, "no_significant_change": 0, "increase": 1}
# effect of each alteration on the quantity asked (the direction it pushes a computed trend)
ALTERATION_SIGN = {"Terra NDVI": -1, "Landsat 8 NDVI": -1, "Terra snow": 1, "Landsat 8 water": 1}
PAIR_GROUP = {"Terra NDVI": "Terra NDVI", "Landsat 8 NDVI": "Landsat 8", "Landsat 8 water": "Landsat 8",
              "Landsat 8 to 7": "Landsat 8", "Terra snow": "Terra snow", "placebo": "Placebo"}


def load_runs(path: str | Path) -> list[dict]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _pct(values) -> float:
    values = list(values)
    return 100.0 * sum(values) / len(values)


class Results:
    """Scored runs of several models, indexed by (model, setting, version, question)."""

    def __init__(self, runs: list[dict], questions: list[dict], references: dict[str, dict]):
        self.questions = {q["id"]: q for q in questions if q["version"] == "original"}
        self.pairs = {(q["id"], q["version"]): q for q in questions if q["version"] != "original"}
        self.references = references
        self.models = sorted({r["model"] for r in runs})
        self.runs = collections.defaultdict(list)
        for r in runs:
            scored = dict(r, **score_run(references[r["question"]], r["answer"]))
            self.runs[(r["model"], r["setting"], r["version"], r["question"])].append(scored)
        for key in self.runs:
            self.runs[key].sort(key=lambda r: r["pass"])

    def ids(self, *classes: str) -> list[str]:
        return sorted(q for q, v in self.questions.items() if v["class"] in classes)

    @property
    def answerable(self) -> list[str]:
        return self.ids("computable", "recognition")

    def pass3(self, model: str, question: str, setting: str = "record", version: str = "original") -> bool:
        runs = self.runs[(model, setting, version, question)]
        return bool(runs) and all(r["right"] for r in runs)

    def score(self, model: str, questions: list[str], setting: str = "record") -> float:
        return _pct(self.pass3(model, q, setting) for q in questions)

    def pair_versions(self, version: str) -> list[str]:
        return sorted(q for q, v in self.pairs if v == version)

    def pair_case(self, model: str, question: str, version: str = "altered") -> str:
        if not self.pass3(model, question):
            return "wrong_on_original"
        if not self.pass3(model, question, version=version):
            return "moved"
        if self.pass3(model, question, setting="closed_book") or self.questions[question]["no_change_reference"]:
            return "held"
        return "beyond"


def majority_class(questions: dict[str, dict], references: dict[str, dict]) -> dict[str, bool]:
    """Leave-one-out majority-class baseline: right (pass^3 of a constant answer) per question."""
    def answer_type(qid):
        conclusion = references[qid]["conclusion"]
        if not isinstance(conclusion, str):
            return ("derived", "recovered" if conclusion[0] == "recovered" else "sign")
        spec = next(f for f in references[qid]["fields"] if f["name"] == conclusion)
        field = next(f for f in questions[qid]["fields"] if f["name"] == conclusion)
        return (spec["kind"], tuple(field.get("options") or field.get("enum") or []))

    def reference_class(qid):
        ref = references[qid]
        conclusion, fields = ref["conclusion"], {f["name"]: f for f in ref["fields"]}
        if isinstance(conclusion, str):
            return json.dumps(fields[conclusion]["reference"])
        if conclusion[0] == "recovered":
            return json.dumps("recovered" if isinstance(fields[conclusion[1]]["reference"], (int, float)) else "not_recovered")
        if conclusion[0] == "sign_diff":
            diff = fields[conclusion[1]]["reference"] - fields[conclusion[2]]["reference"]
            return json.dumps((diff > 0) - (diff < 0))
        x = fields[conclusion[1]]["reference"] - (1.0 if conclusion[0] == "sign_ratio" else 0.0)
        return json.dumps((x > 0) - (x < 0))

    signature = {q: (answer_type(q), reference_class(q)) for q in references}  # in reference file order
    right = {}
    for qid, ref in references.items():
        kind, conclusion = signature[qid][0], ref["conclusion"]
        if kind[0] == "num":
            right[qid] = False
            continue
        peers = collections.Counter(c for q2, (k2, c) in signature.items() if q2 != qid and k2 == kind)
        if peers:
            value = json.loads(peers.most_common(1)[0][0])
        else:
            options = list(kind[1]) if len(kind) > 1 and kind[1] else []
            value = next((o for o in options if o.startswith("no_") or o == "stable"), options[0] if options else None)
        if isinstance(conclusion, str):
            answer = {conclusion: value}
        elif conclusion[0] == "recovered":
            answer = {conclusion[1]: 1.0 if value == "recovered" else None}
        elif conclusion[0] == "sign_diff":
            answer = {conclusion[1]: float(value or 0) * 1e6, conclusion[2]: 0.0}
        else:
            answer = {conclusion[1]: (1.0 if conclusion[0] == "sign_ratio" else 0.0) + float(value or 0) * 1e6}
        right[qid] = is_right(ref, answer)
    return right


def always_no_change(questions: dict[str, dict], references: dict[str, dict]) -> dict[str, bool]:
    """Always answer no change where the conclusion offers it; elsewhere no answer."""
    right = {}
    for qid, ref in references.items():
        conclusion = ref["conclusion"]
        options = []
        if isinstance(conclusion, str):
            field = next(f for f in questions[qid]["fields"] if f["name"] == conclusion)
            options = field.get("options") or field.get("enum") or []
        value = next((o for o in NO_CHANGE if o in options), None)
        right[qid] = bool(value) and is_right(ref, {conclusion: value})
    return right


def _auroc(positive: list[float], negative: list[float]) -> float | None:
    if not positive or not negative:
        return None
    wins = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in positive for b in negative)
    return wins / (len(positive) * len(negative))


def main_table(res: Results) -> dict:
    """Table 2: pass^3 on the 226 questions with a 95% bootstrap interval, and by analysis task."""
    qs = res.answerable
    tasks = collections.defaultdict(list)
    for q in qs:
        tasks[res.questions[q]["task"]].append(q)
    rng = random.Random(BOOTSTRAP_SEED)
    rows = {}
    for m in res.models:
        solved = [res.pass3(m, q) for q in qs]
        boot = sorted(_pct(rng.choice(solved) for _ in solved) for _ in range(BOOTSTRAP_SAMPLES))
        rows[m] = {"overall": _pct(solved), "interval": [boot[49], boot[1949]],
                   "tasks": {t: res.score(m, ids) for t, ids in tasks.items()}}
    baselines = {}
    for name, right in (("Majority class", majority_class(res.questions, res.references)),
                        ("Always no change", always_no_change(res.questions, res.references))):
        baselines[name] = {"overall": _pct(right[q] for q in qs), "tasks": {t: _pct(right[q] for q in ids) for t, ids in tasks.items()}}
    median = {t: statistics.median(rows[m]["tasks"][t] for m in res.models) for t in tasks}
    return {"questions": len(qs), "task_order": sorted(tasks, key=lambda t: median[t]),
            "task_questions": {t: len(v) for t, v in tasks.items()}, "models": rows, "baselines": baselines}


def behavior_table(res: Results) -> dict:
    """Table 3: accuracy, consistency, confidence, abstention and effort, with the record."""
    qs, rec, ie = res.answerable, res.ids("recognition"), res.ids("insufficient_evidence")
    out = {}
    for m in res.models:
        runs = [r for q in qs for r in res.runs[(m, "record", "original", q)]]
        rights = collections.Counter(sum(r["right"] for r in res.runs[(m, "record", "original", q)]) for q in qs)
        answered = [r for r in runs if not r["abstained"] and r["confidence"] is not None]
        rec_runs = [r for q in rec for r in res.runs[(m, "record", "original", q)]]
        ie_runs = [r for q in ie for r in res.runs[(m, "record", "original", q)]]
        out[m] = {
            "one_run": _pct(r["right"] for r in runs),
            "pass3": res.score(m, qs),
            "right_in_one_or_two": rights[1] + rights[2],
            "auroc": _auroc([r["confidence"] for r in answered if r["right"]],
                            [r["confidence"] for r in answered if not r["right"]]),
            "recognition_abstention": _pct(r["abstained"] for r in rec_runs),
            "insufficient_evidence_abstained": sum(r["right"] for r in ie_runs),
            "insufficient_evidence_runs": len(ie_runs),
            "tool_calls": statistics.mean(r["tool_calls"] or 0 for r in runs),
            "minutes": statistics.mean(r["working_time_s"] or 0 for r in runs) / 60,
            "image_views": statistics.mean(r["image_views"] or 0 for r in runs),
        }
    return out


def controls_table(res: Results) -> dict:
    """Table 4: closed book and record by class, and outcomes on the instrument and placebo pairs."""
    classes = {"computable": res.ids("computable"), "recognition": res.ids("recognition")}
    altered, placebo = res.pair_versions("altered"), res.pair_versions("placebo")
    out = {"models": {}, "baselines": {}}
    for m in res.models:
        row = {c: {"closed_book": res.score(m, ids, "closed_book"), "record": res.score(m, ids)} for c, ids in classes.items()}
        cases = collections.Counter(res.pair_case(m, q) for q in altered)
        row["pairs"] = {"right": cases["moved"] + cases["held"] + cases["beyond"], "moved": cases["moved"],
                        "held": cases["held"], "beyond": cases["beyond"]}
        p = collections.Counter(res.pair_case(m, q, "placebo") for q in placebo)
        row["placebo"] = {"right": p["moved"] + p["held"] + p["beyond"], "moved": p["moved"]}
        out["models"][m] = row
    for name, right in (("Majority class", majority_class(res.questions, res.references)),
                        ("Always no change", always_no_change(res.questions, res.references))):
        out["baselines"][name] = {c: _pct(right[q] for q in ids) for c, ids in classes.items()}
        out["baselines"][name].update({"pairs_right": sum(right[q] for q in altered),
                                        "placebo_right": sum(right[q] for q in placebo)})
    return out


def reference_types(res: Results) -> dict:
    """Figure 4: pass^3 on questions computed from record variables and on questions that need a map."""
    groups = {"method": "computed from the record", "withheld_product": "mapping"}
    ids = {k: [q for q in res.answerable if res.questions[q]["reference_source"] == k] for k in groups}
    return {"questions": {groups[k]: len(v) for k, v in ids.items()},
            "models": {m: {groups[k]: res.score(m, v) for k, v in ids.items()} for m in res.models}}


def pair_outcomes(res: Results) -> dict:
    """Figure 6 and Section 4.2: case outcomes by altered satellite, direction of changed answers, placebo changes."""
    groups = collections.defaultdict(collections.Counter)
    for version in ("altered", "placebo"):
        for q in res.pair_versions(version):
            group = PAIR_GROUP[res.pairs[(q, version)]["alteration"]["type"]]
            for m in res.models:
                groups[group][res.pair_case(m, q, version)] += 1
    direction = collections.Counter()
    for q in res.pair_versions("altered"):
        sign = ALTERATION_SIGN.get(res.pairs[(q, "altered")]["alteration"]["type"])
        if sign is None:
            continue
        for m in res.models:
            original = res.runs[(m, "record", "original", q)]
            changed = res.runs[(m, "record", "altered", q)]
            for a, b in zip(original, changed):
                da = (a["answer"] or {}).get("direction")
                db = (b["answer"] or {}).get("direction")
                if da in DIRECTION_ORDER and db in DIRECTION_ORDER and da != db:
                    with_alteration = (DIRECTION_ORDER[db] - DIRECTION_ORDER[da] > 0) == (sign > 0)
                    direction["with" if with_alteration else "against"] += 1
    instrument = {k: v for k, v in groups.items() if k != "Placebo"}
    right = sum(v["moved"] + v["held"] + v["beyond"] for v in instrument.values())
    return {
        "groups": {k: {"moved": v["moved"], "right": v["moved"] + v["held"] + v["beyond"], "held": v["held"],
                       "beyond": v["beyond"]} for k, v in groups.items()},
        "moved_share": 100.0 * sum(v["moved"] for v in instrument.values()) / right,
        "beyond_share": 100.0 * sum(v["beyond"] for v in instrument.values()) / right,
        "placebo_moved_share": 100.0 * groups["Placebo"]["moved"] / (
            groups["Placebo"]["moved"] + groups["Placebo"]["held"] + groups["Placebo"]["beyond"]),
        "changed_answers_with_alteration": dict(direction),
    }


STEPS = ("Data", "Time sampling", "Question", "Analysis", "Close call", "Unfinished", "Other")
REPORTS = ("attributed_to_instrument", "break_not_attributed", "reported_separately", "generic_caveat", "no_mention")


def leading_models(res: Results, n: int = 6) -> list[str]:
    """The n models with the highest pass^3 on the 226 questions."""
    return sorted(res.models, key=lambda m: -res.score(m, res.answerable))[:n]


def failure_steps(rows: list[dict], leading: list[str]) -> dict:
    """Appendix B.8: first wrong step of the coded failed runs, for the leading models and the others."""
    out = {"leading": collections.Counter(), "other": collections.Counter()}
    for r in rows:
        out["leading" if r["model"] in leading else "other"][r["step"]] += 1
    return {k: {s: v[s] for s in STEPS} for k, v in out.items()}


def sensor_reports(rows: list[dict]) -> dict:
    """Appendix C.5: what the coded runs on instrument pairs say about the sensors, by case."""
    counts = {case: collections.Counter(r["report"] for r in rows if r["case"] == case) for case in ("moved", "beyond")}
    moved = sum(counts["moved"].values())
    reported = counts["moved"]["break_not_attributed"] + counts["moved"]["attributed_to_instrument"]
    return {"counts": {case: {k: c[k] for k in REPORTS} for case, c in counts.items()},
            "moved_runs_reporting_the_break": 100.0 * reported / moved,
            "moved_runs_attributing_it_to_the_instrument": 100.0 * counts["moved"]["attributed_to_instrument"] / moved}
