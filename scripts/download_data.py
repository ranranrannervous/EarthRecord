"""Download the EarthRecord dataset from Hugging Face and unpack the views the agents work on.

    python scripts/download_data.py                                # all questions and all views (about 680 GB)
    python scripts/download_data.py --versions original            # without the instrument-pair views
    python scripts/download_data.py --ids a14-5,r-gao-4            # only the views these questions need

The dataset is gated: accept its terms on the Hugging Face page once and log in (`hf auth login`) before downloading.
Each view is checked file by file against the published SHA-256 checksums (skip with --no-verify).
"""

import argparse
import gzip
import hashlib
import json
import os
import shutil
import tarfile
import time
from pathlib import Path

from huggingface_hub import hf_hub_download

DATASET = os.environ.get("EARTHRECORD_DATASET", "haoranranranran/EarthRecord")


def fetch(name: str, data_dir: Path, attempts: int = 5) -> Path:
    """Download one file of the dataset, retrying on network errors."""
    for attempt in range(1, attempts + 1):
        try:
            return Path(hf_hub_download(DATASET, name, repo_type="dataset", local_dir=data_dir / ".download"))
        except Exception as error:  # network errors surface under several exception types
            if attempt == attempts:
                raise
            print("  retrying %s after: %s" % (name, str(error).splitlines()[0][:120]), flush=True)
            time.sleep(10 * attempt)


def unpack(archive: Path, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(target, filter="tar")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(view: Path, checksums: Path):
    expected = {}
    with gzip.open(checksums, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            expected[r["path"]] = (r["bytes"], r["sha256"])
    found = {str(p.relative_to(view)) for p in view.rglob("*") if p.is_file()}
    if found != set(expected):
        raise SystemExit("%s: %d files missing, %d unexpected" % (view, len(set(expected) - found), len(found - set(expected))))
    for rel, (size, digest) in expected.items():
        path = view / rel
        if path.stat().st_size != size or sha256(path) != digest:
            raise SystemExit("%s: checksum mismatch for %s" % (view, rel))


def build_site(site: str, data_dir: Path, keep: bool):
    target = data_dir / "views" / site
    if target.exists():
        return
    archive = fetch("sites/%s.tar" % site, data_dir)
    unpack(archive, target.with_name(site + ".partial"))
    target.with_name(site + ".partial").rename(target)
    if not keep:
        archive.unlink()


def build_altered(view: str, site: str, data_dir: Path, keep: bool):
    """An altered or placebo view: the site's files, minus the removed ones, with the altered files replaced."""
    target = data_dir / "views" / view
    if target.exists():
        return
    partial = target.with_name(view + ".partial")
    if partial.exists():
        shutil.rmtree(partial)
    shutil.copytree(data_dir / "views" / site, partial, copy_function=shutil.copy2)
    for rel in fetch("altered/%s.removed.txt" % view, data_dir).read_text().splitlines():
        if rel:
            (partial / rel).unlink()
    archive = fetch("altered/%s.tar" % view, data_dir)
    unpack(archive, partial)
    for d in sorted((p for p in partial.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    partial.rename(target)
    if not keep:
        archive.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--versions", default="original,altered,placebo")
    parser.add_argument("--ids", help="comma-separated question ids (default: all)")
    parser.add_argument("--keep-archives", action="store_true", help="keep the downloaded .tar files")
    parser.add_argument("--no-verify", action="store_true", help="skip the checksum check")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("questions.jsonl", "references.jsonl"):
        shutil.copy2(fetch(name, data_dir), data_dir / name)
    versions = {v.strip() for v in args.versions.split(",")}
    ids = {i.strip() for i in args.ids.split(",")} if args.ids else None
    questions = [json.loads(line) for line in open(data_dir / "questions.jsonl", encoding="utf-8")]
    site_of = {q["id"]: q["view"] for q in questions if q["version"] == "original"}
    wanted = [q for q in questions if q["version"] in versions and (ids is None or q["id"] in ids)]
    sites = sorted({site_of[q["id"]] for q in wanted})
    altered = sorted({(q["view"], site_of[q["id"]]) for q in wanted if q["version"] != "original"})

    for i, site in enumerate(sites, 1):
        print("[%d/%d] %s" % (i, len(sites), site), flush=True)
        build_site(site, data_dir, args.keep_archives)
        if not args.no_verify:
            verify(data_dir / "views" / site, fetch("checksums/%s.jsonl.gz" % site, data_dir))
    for i, (view, site) in enumerate(altered, 1):
        print("[%d/%d] %s" % (i, len(altered), view), flush=True)
        build_altered(view, site, data_dir, args.keep_archives)
        if not args.no_verify:
            verify(data_dir / "views" / view, fetch("checksums/%s.jsonl.gz" % view, data_dir))
    print("Done: %d site views and %d instrument-pair views in %s" % (len(sites), len(altered), data_dir / "views"))


if __name__ == "__main__":
    main()
