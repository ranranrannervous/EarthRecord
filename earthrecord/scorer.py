"""Inspect scorer. Scoring runs in the host process; the sandbox never sees a reference answer."""

import json
from pathlib import Path

from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import TaskState
from inspect_ai.util import OutputLimitExceededError, sandbox

from .scoring import score_run

ARCHIVE_ALL = ["tar", "czf", "/tmp/work.tar.gz", "-C", "/work", "."]
# a /work too large to read back keeps its scripts and logs (files under 1 MB)
ARCHIVE_SMALL = ["sh", "-c", "cd /work && find . -type f -size -1024k -print0 | tar czf /tmp/work.tar.gz --null -T -"]


def _parse(text: str):
    try:
        answer = json.loads(text)
    except (TypeError, ValueError):
        return None
    return answer if isinstance(answer, dict) else None


async def _archive_work(state: TaskState, out_dir: Path) -> str | None:
    """Save the run's /work directory (the agent's scripts, outputs and figures) next to the log."""
    out = out_dir / ("%s-pass%d.tar.gz" % (state.sample_id, state.epoch))
    for command in (ARCHIVE_ALL, ARCHIVE_SMALL):
        if not (await sandbox().exec(command)).success:
            continue
        try:
            data = await sandbox().read_file("/tmp/work.tar.gz", text=False)
        except OutputLimitExceededError:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return str(out)
    return None


@scorer(metrics=[mean()])
def earthrecord_scorer(references: dict[str, dict], work_archive_dir: str | None = None):
    """1 when the run is right (see earthrecord.scoring), else 0. The parsed answer and its scores go to the metadata."""

    async def score(state: TaskState, target: Target) -> Score:
        answer = _parse(state.output.completion)
        result = score_run(references[state.metadata["pair"]], answer)
        archive = None
        if work_archive_dir and state.metadata.get("sandboxed", True):
            archive = await _archive_work(state, Path(work_archive_dir))
        conclusion = None
        if answer is not None:
            reference = references[state.metadata["pair"]]
            name = reference["conclusion"] if isinstance(reference["conclusion"], str) else reference["conclusion"][1]
            conclusion = answer.get(name)
        return Score(
            value=1 if result["right"] else 0,
            answer=json.dumps(conclusion) if conclusion is not None else None,
            explanation=None if answer is not None else "the answer is not a JSON object",
            metadata={"answer": answer, "abstained": result["abstained"],
                      "question_score": result["question_score"], "field_scores": result["field_scores"],
                      "work_archive": archive},
        )

    return score
