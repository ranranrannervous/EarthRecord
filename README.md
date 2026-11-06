# EarthRecord

**From Pixels to Land Change with Multimodal Agents over Four Decades of Satellite Imagery**

EarthRecord evaluates whether multimodal agents can turn four decades of raw, multi-sensor satellite records into
reliable land-change analysis. For each question, an agent works in an offline sandbox with Python, a shell and an image
viewer on the record of one site as distributed by its providers: Landsat, MODIS, VIIRS and Sentinel-2 data with
ancillary layers, clipped but with their values unmodified. Data selection, cloud masking, scaling, mapping and
cross-sensor harmonization are left to the agent, and answers are scored against reference answers it never sees.

- **56 sites** (48 core areas and 8 administrative regions), 1984 to 2026.
- **238 questions** over ten analysis tasks: 153 computable from the record, 73 asking what is on the ground, 12 with
  insufficient evidence.
- **Two controls**: the *closed book* removes the record, and **22 instrument pairs** alter one satellite's data while
  nothing changes on the ground (with 8 placebo pairs).

This repository holds the evaluation sandbox, the scoring, the results of twelve models and the scripts that reproduce
the paper's tables. The data are on Hugging Face: [haoranranranran/EarthRecord](https://huggingface.co/datasets/haoranranranran/EarthRecord).

## Results

pass^3 (%): a question counts when the conclusion is right in all three passes. Overall: the 226 computable and
recognition questions with the record. Moved: right answers on instrument pairs that turn wrong when one satellite's
data are altered.

| Model | Overall [95% CI] | Computable, closed book | Computable, record | Recognition, closed book | Recognition, record | Moved |
|---|---|---|---|---|---|---|
| Opus 5.5 | 85.4 [80.5, 89.8] | 62.1 | 87.6 | 65.8 | 80.8 | 7/21 |
| GPT-6 Sol | 84.1 [79.2, 88.9] | 49.0 | 86.9 | 57.5 | 78.1 | 11/19 |
| GPT-6.1 Sol | 81.4 [76.1, 86.3] | 37.9 | 89.5 | 60.3 | 64.4 | 10/20 |
| Sonnet 5.5 | 81.0 [75.7, 86.3] | 54.2 | 85.0 | 53.4 | 72.6 | 13/22 |
| GPT-6 Astra | 77.0 [71.2, 82.3] | 34.0 | 87.6 | 58.9 | 54.8 | 11/21 |
| GPT-6.1 Terra | 73.5 [67.7, 79.2] | 25.5 | 86.3 | 46.6 | 46.6 | 10/19 |
| Gemini 3 Flash | 72.6 [66.8, 77.9] | 49.7 | 76.5 | 52.1 | 64.4 | 9/17 |
| DeepSeek Flash | 68.1 [61.9, 74.3] | 37.9 | 80.4 | 52.1 | 42.5 | 6/17 |
| Kimi K2.5 | 54.0 [47.8, 60.6] | 16.3 | 62.7 | 30.1 | 35.6 | 8/15 |
| Haiku 5.5 | 41.2 [35.0, 47.8] | 25.5 | 49.7 | 43.8 | 23.3 | 8/13 |
| Qwen 3.7 Flash | 19.5 [14.6, 24.8] | 4.6 | 20.9 | 9.6 | 16.4 | 7/8 |
| GPT-6 Luna | 18.6 [13.7, 23.9] | 12.4 | 17.0 | 27.4 | 21.9 | 7/8 |
| *Majority class* | 23.9 | - | 24.2 | - | 23.3 | - |

## Installation

```
git clone https://github.com/ranranrannervous/EarthRecord && cd EarthRecord
pip install -e ".[providers]"
docker build -t earthrecord-sandbox:1.0 sandbox/
```

Running models needs Docker (Linux recommended), 4 CPUs and 24 GB of memory per concurrent run, and the API keys of the
providers you use (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`; for OpenAI-compatible services such as
DeepSeek, Moonshot and DashScope, `<SERVICE>_API_KEY` and `<SERVICE>_BASE_URL`).

## Data

The dataset is gated: accept its terms on the [dataset page](https://huggingface.co/datasets/haoranranranran/EarthRecord) and
log in with `hf auth login`. Then download and unpack:

```
python scripts/download_data.py                          # all views: about 680 GB, 1.1 TB unpacked with the pair views
python scripts/download_data.py --versions original      # without the instrument-pair views
python scripts/download_data.py --ids a14-5,r-gao-4      # only the views these questions need
```

Every view is checked file by file against its published SHA-256 checksums. See [docs/data.md](docs/data.md) for the
layout and the question and reference formats.

## Running

```
python scripts/run.py --models "Opus 5.5" --setting record                       # the main evaluation
python scripts/run.py --models "Opus 5.5" --setting closed_book                  # the closed book
python scripts/run.py --models "Opus 5.5" --setting record --versions altered,placebo   # instrument and placebo pairs
```

Models and their settings are in [configs/models.yaml](configs/models.yaml); add your own by its
[Inspect](https://inspect.aisi.org.uk/) model name. Every question runs for three passes with 3,600 s of working time
and 300 messages per run. The task can also be run directly with Inspect:

```
inspect eval earthrecord/earthrecord --model anthropic/claude-opus-5-5 -T data_dir=data -T setting=record
```

Inspect reports the mean over runs and `at_least_3`, which is pass^3. Logs go to `logs/`.

## Reproducing the paper

```
python scripts/reproduce.py --data-dir data
```

prints Tables 2 to 4, the data of Figures 4 and 6, the instrument-pair shares of Section 4.2, the runs without the image
viewer, and the failure steps and sensor reports of the appendix, from the released results in [results/](results/).
It needs only `questions.jsonl` and `references.jsonl` from the dataset, not the views. See
[docs/results.md](docs/results.md) for the result files and [docs/scoring.md](docs/scoring.md) for the scoring.

## Repository

```
earthrecord/        task, agent, tools, sandbox, scoring and analysis
sandbox/            Dockerfile of the agent sandbox
configs/            the twelve models of the paper
scripts/            run.py, download_data.py, reproduce.py
results/            per-run results of the twelve models and the appendix codings
docs/               data, scoring and result formats
tests/
```

## Citation

```bibtex
@misc{zhang2026earthrecord,
  title  = {{EarthRecord}: From Pixels to Land Change with Multimodal Agents over Four Decades of Satellite Imagery},
  author = {Zhang, Haoran and Sun, Huizhen and Wen, Hanbin and Leng, Jie and Zhu, Jiaxin and Sun, Zhaohua},
  year   = {2026}
}
```

## License

Code: Apache-2.0. The questions, reference answers and checksums are released under CC BY 4.0; the satellite,
reanalysis and map data keep the licences of their providers, listed on the dataset page.
