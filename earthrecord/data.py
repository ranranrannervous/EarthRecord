"""Access to the EarthRecord dataset.

Layout of the data directory (see docs/data.md):

    questions.jsonl     one line per question version: id, version (original, altered, placebo), pair (the original
                        question of an altered or placebo version), view, question, location, fields, canary and labels
    references.jsonl    one line per original question: conclusion rule and reference fields
    views/<view>/       the files an agent sees at /data for that view
"""

import json
from pathlib import Path

VERSIONS = ("original", "altered", "placebo")


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_questions(data_dir: str | Path, versions: tuple[str, ...] = ("original",)) -> list[dict]:
    """Question versions of the benchmark, in file order."""
    unknown = set(versions) - set(VERSIONS)
    if unknown:
        raise ValueError("unknown versions: %s" % ", ".join(sorted(unknown)))
    return [q for q in _read_jsonl(Path(data_dir) / "questions.jsonl") if q["version"] in versions]


def load_references(data_dir: str | Path) -> dict[str, dict]:
    """Reference answers by original question id. Altered and placebo versions are scored against their original."""
    return {r["id"]: r for r in _read_jsonl(Path(data_dir) / "references.jsonl")}


def view_dir(data_dir: str | Path, view: str) -> Path:
    path = Path(data_dir) / "views" / view
    if not path.is_dir():
        raise FileNotFoundError("view not found: %s (download the dataset first, see README)" % path)
    return path
