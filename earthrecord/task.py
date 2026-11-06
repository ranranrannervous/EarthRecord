"""The EarthRecord task for Inspect.

Settings:
- record: the agent works on the question's view of the raw record in a sandbox (the main evaluation);
- closed_book: the question and the site's bounding box only, no data and no tools;
- no_image: the record without the image viewer.

Versions: original questions, and the altered and placebo versions of the instrument pairs (scored against the original
question's reference). Every question is run for three passes; a question counts as solved when all three are right.
"""

from pathlib import Path

from inspect_ai import Epochs, Task, task
from inspect_ai.dataset import Sample

from .agent import SETTINGS, earthrecord_solver
from .data import VERSIONS, load_questions, load_references, view_dir
from .sandbox import IMAGE, compose_file
from .scorer import earthrecord_scorer

WORKING_LIMIT = 3600  # seconds of working time per run
MESSAGE_LIMIT = 300
PASSES = 3


def _samples(data_dir: Path, setting: str, versions: tuple[str, ...], ids: set[str] | None, image: str) -> list[Sample]:
    samples = []
    for q in load_questions(data_dir, versions):
        if ids and q["id"] not in ids:
            continue
        sample_id = q["id"] if q["version"] == "original" else "%s-%s" % (q["id"], q["version"])
        metadata = {"pair": q["pair"], "version": q["version"], "fields": q["fields"]}
        if setting == "closed_book":
            samples.append(Sample(id=sample_id, input=q["question"] + "\n\n" + q["location"], target="",
                                  metadata=dict(metadata, sandboxed=False)))
            continue
        # the compose file sits outside the view, so the agent cannot read it
        compose = compose_file(view_dir(data_dir, q["view"]), data_dir / ".sandbox" / ("%s.yaml" % q["view"]), image)
        samples.append(Sample(id=sample_id, input=q["question"], target="", sandbox=("docker", compose),
                              metadata=metadata))
    return samples


@task
def earthrecord(data_dir: str = "data", setting: str = "record", versions: str = "original",
                passes: int = PASSES, ids: str | None = None, working_limit: int = WORKING_LIMIT,
                message_limit: int = MESSAGE_LIMIT, image: str = IMAGE, work_archive_dir: str | None = None) -> Task:
    """EarthRecord.

    Args:
        data_dir: The downloaded dataset (questions.jsonl, references.jsonl, views/).
        setting: record, closed_book or no_image.
        versions: Comma-separated versions to run: original, altered, placebo.
        passes: Passes per question (the paper uses 3).
        ids: Optional comma-separated question ids to run.
        working_limit: Working time limit per run in seconds.
        message_limit: Message limit per run.
        image: Sandbox image built from sandbox/Dockerfile.
        work_archive_dir: Optional directory to keep each run's /work as a .tar.gz.
    """
    if setting not in SETTINGS:
        raise ValueError("setting must be one of %s" % ", ".join(SETTINGS))
    chosen = tuple(v.strip() for v in versions.split(",") if v.strip())
    if setting == "closed_book" and set(chosen) != {"original"}:
        raise ValueError("the closed book runs the original questions only")
    if set(chosen) - set(VERSIONS):
        raise ValueError("versions must be among %s" % ", ".join(VERSIONS))
    data_dir_path = Path(data_dir).resolve()
    selected = {i.strip() for i in ids.split(",")} if ids else None
    return Task(
        dataset=_samples(data_dir_path, setting, chosen, selected, image),
        solver=earthrecord_solver(setting),
        scorer=earthrecord_scorer(load_references(data_dir_path), work_archive_dir),
        working_limit=working_limit,
        message_limit=message_limit,
        epochs=Epochs(passes, ["mean", "at_least_%d" % passes]),  # at_least_3 is pass^3
    )
