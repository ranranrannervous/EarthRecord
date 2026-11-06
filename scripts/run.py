"""Run EarthRecord for models listed in configs/models.yaml.

    python scripts/run.py --models "Opus 5.5" --setting record --versions original
    python scripts/run.py --models all --setting closed_book

Settings and limits follow the paper: three passes per question, 3,600 s of working time and 300 messages per run, and
eight runs at a time.
"""

import argparse

import yaml
from inspect_ai import eval as inspect_eval

from earthrecord.task import earthrecord


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="configs/models.yaml")
    parser.add_argument("--models", default="all", help="comma-separated names from the config, or all")
    parser.add_argument("--setting", default="record", choices=["record", "closed_book", "no_image"])
    parser.add_argument("--versions", default="original", help="comma-separated: original, altered, placebo")
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--max-samples", type=int, default=8)
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args()

    models = yaml.safe_load(open(args.config))["models"]
    if args.models != "all":
        wanted = {m.strip() for m in args.models.split(",")}
        unknown = wanted - {m["name"] for m in models}
        if unknown:
            raise SystemExit("not in %s: %s" % (args.config, ", ".join(sorted(unknown))))
        models = [m for m in models if m["name"] in wanted]

    for m in models:
        config = {}
        if m.get("reasoning_effort", "default") != "default":
            config["reasoning_effort"] = m["reasoning_effort"]
        task = earthrecord(data_dir=args.data_dir, setting=args.setting, versions=args.versions, passes=args.passes)
        inspect_eval(task, model=m["model"], model_args=m.get("model_args", {}),
                     log_dir="%s/%s" % (args.log_dir, args.setting), max_samples=args.max_samples,
                     fail_on_error=False, retry_on_error=3, attempt_timeout=1800, **config)


if __name__ == "__main__":
    main()
