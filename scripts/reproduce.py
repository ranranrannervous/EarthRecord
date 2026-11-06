"""Reproduce the paper's tables and figure data from the released results.

    python scripts/reproduce.py --data-dir data                 # Markdown tables on stdout
    python scripts/reproduce.py --data-dir data --json out.json # also every number as JSON

The results of the twelve models are in results/runs.jsonl.gz (one line per run) and results/no_image.csv (the runs
without the image viewer, per question). Questions and reference answers come from the dataset (see README).
"""

import argparse
import csv
import json
from pathlib import Path

import yaml

from earthrecord.analysis import (STEPS, Results, behavior_table, controls_table, failure_steps, leading_models, load_runs,
                                  main_table, pair_outcomes, reference_types, sensor_reports)
from earthrecord.data import load_questions, load_references

ROOT = Path(__file__).resolve().parents[1]


def model_names(config: Path) -> dict[str, str]:
    return {m["model"].rsplit("/", 1)[-1]: m["name"] for m in yaml.safe_load(open(config))["models"]}


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def f1(x) -> str:
    return "-" if x is None else "%.1f" % x


def gain(x: float) -> str:
    return "0.0" if round(x, 1) == 0 else "%+.1f" % x


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--results", default=str(ROOT / "results"))
    parser.add_argument("--config", default=str(ROOT / "configs/models.yaml"))
    parser.add_argument("--json", help="write every number to this JSON file")
    args = parser.parse_args()

    res = Results(load_runs(Path(args.results) / "runs.jsonl.gz"),
                  load_questions(args.data_dir, ("original", "altered", "placebo")), load_references(args.data_dir))
    name = model_names(Path(args.config))
    t2, t3, t4 = main_table(res), behavior_table(res), controls_table(res)
    fig4, fig6 = reference_types(res), pair_outcomes(res)
    order = sorted(res.models, key=lambda m: -t2["models"][m]["overall"])

    tasks = t2["task_order"]
    print("## Table 2. Results by analysis task (pass^3, %%, %d questions)\n" % t2["questions"])
    rows = [[name[m], "%s [%s, %s]" % (f1(t2["models"][m]["overall"]), f1(t2["models"][m]["interval"][0]),
                                       f1(t2["models"][m]["interval"][1]))] + [f1(t2["models"][m]["tasks"][t]) for t in tasks]
            for m in order]
    rows += [[b, f1(v["overall"])] + [f1(v["tasks"][t]) for t in tasks] for b, v in t2["baselines"].items()]
    print(table(["Model", "Overall [95% CI]"] + ["%s (%d)" % (t, t2["task_questions"][t]) for t in tasks], rows))

    print("\n## Table 3. Agent behavior and effort\n")
    rows = [[name[m], f1(t3[m]["one_run"]), f1(t3[m]["pass3"]), t3[m]["right_in_one_or_two"], "%.2f" % t3[m]["auroc"],
             f1(t3[m]["recognition_abstention"]), "%d" % t3[m]["insufficient_evidence_abstained"],
             f1(t3[m]["tool_calls"]), f1(t3[m]["minutes"]), "%.2f" % t3[m]["image_views"]] for m in order]
    print(table(["Model", "One run", "pass^3", "Right in one or two passes (of 226)", "AUROC",
                 "Recognition runs abstaining (%)", "Insufficient-evidence runs abstaining (of 36)", "Tool calls",
                 "Minutes", "Image views"], rows))

    print("\n## Table 4. Answer sources and outcomes on instrument pairs\n")
    rows = []
    for m in order:
        d = t4["models"][m]
        rows.append([name[m]] + [x for c in ("computable", "recognition") for x in (
            f1(d[c]["closed_book"]), f1(d[c]["record"]), gain(d[c]["record"] - d[c]["closed_book"]))] +
            ["%d/%d" % (d["pairs"]["moved"], d["pairs"]["right"]), d["pairs"]["held"], d["pairs"]["beyond"],
             "%d/%d" % (d["placebo"]["moved"], d["placebo"]["right"])])
    for b, v in t4["baselines"].items():
        constant = lambda n: "0/%d" % n if n else "-"  # a constant answer never moves
        rows.append([b, "-", f1(v["computable"]), "-", "-", f1(v["recognition"]), "-",
                     constant(v["pairs_right"]), v["pairs_right"], "-", constant(v["placebo_right"])])
    print(table(["Model", "Computable closed", "Computable record", "Gain", "Recognition closed", "Recognition record",
                 "Gain", "Moved", "Held", "Beyond", "Placebo moved"], rows))

    print("\n## Figure 4. pass^3 (%%) by reference type (%s)\n" % ", ".join(
        "%s: %d questions" % kv for kv in fig4["questions"].items()))
    print(table(["Model"] + list(fig4["questions"]),
                [[name[m]] + [f1(fig4["models"][m][k]) for k in fig4["questions"]] for m in order]))

    print("\n## Figure 6 and Section 4.2. Instrument-pair outcomes, pooled over models\n")
    print(table(["Altered satellite", "Moved / right on the original", "Held", "Beyond"],
                [[g, "%d/%d" % (v["moved"], v["right"]), v["held"], v["beyond"]] for g, v in fig6["groups"].items()]))
    d = fig6["changed_answers_with_alteration"]
    print("\nRight answers that move: %.1f%%; hold beyond both: %.1f%%; placebo answers that move: %.1f%%; "
          "changed directions that follow the alteration: %.1f%%." % (
              fig6["moved_share"], fig6["beyond_share"], fig6["placebo_moved_share"],
              100.0 * d.get("with", 0) / max(1, d.get("with", 0) + d.get("against", 0))))

    no_image = list(csv.DictReader(open(Path(args.results) / "no_image.csv")))
    print("\n## Without the image viewer: recognition questions right in all three passes\n")
    counts = {}
    for r in no_image:
        c = counts.setdefault(r["model"], [0, 0, 0, 0])
        c[0] += 1
        c[1] += int(r["right_with_image"])
        c[2] += int(r["right_without_image"])
        c[3] += int(r["right_closed_book"])
    print(table(["Model", "Questions", "With the image viewer", "Without", "Closed book"],
                [[name[m]] + c for m, c in counts.items()]))

    steps = failure_steps(list(csv.DictReader(open(Path(args.results) / "failure_steps.csv"))), leading_models(res))
    print("\n## Appendix B.8. First wrong step of 144 coded failed runs\n")
    print(table(["Step", "Leading six", "Other six"], [[s, steps["leading"][s], steps["other"][s]] for s in STEPS]))

    reports = sensor_reports(list(csv.DictReader(open(Path(args.results) / "sensor_reports.csv"))))
    print("\n## Appendix C.5. What runs on instrument pairs say about the sensors\n")
    print(table(["Report", "Moved (wrong runs)", "Beyond both"],
                [[k, reports["counts"]["moved"][k], reports["counts"]["beyond"][k]] for k in reports["counts"]["moved"]]))
    print("\nWrong runs in moved cases that report the break: %.1f%%; that attribute it to the instrument: %.1f%%." % (
        reports["moved_runs_reporting_the_break"], reports["moved_runs_attributing_it_to_the_instrument"]))

    if args.json:
        Path(args.json).write_text(json.dumps({"table2": t2, "table3": t3, "table4": t4, "figure4": fig4,
                                               "pairs": fig6, "failure_steps": steps, "sensor_reports": reports}, indent=1))


if __name__ == "__main__":
    main()
