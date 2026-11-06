# Results

The results of the twelve models in the paper. `scripts/reproduce.py` computes every table from these files and the
dataset's `questions.jsonl` and `references.jsonl`.

## runs.jsonl.gz

One line per run: 238 questions with the record and in the closed book, and the 22 altered and 8 placebo versions with the
record, three passes each, for each of the twelve models (18,216 runs).

| Field | Meaning |
|---|---|
| `model` | Model identifier |
| `setting` | `record` or `closed_book` |
| `version` | `original`, `altered` or `placebo` |
| `question` | Question id |
| `pass` | 1, 2 or 3 |
| `status` | `ok`, or `timeout` when the run reached its working-time or message limit before submitting |
| `answer` | The submitted answer: the question's fields, `confidence`, `datasets_used`, `method_summary`, `caveats` |
| `working_time_s` | Working time of the run in seconds |
| `tool_calls`, `messages`, `image_views` | Tool calls, messages, and calls of the image viewer |
| `input_tokens`, `output_tokens` | Tokens reported by the provider |

## no_image.csv

The 73 recognition questions run without the image viewer by three models: one line per model and question, with
whether the question is right in all three passes with the image viewer, without it, and in the closed book.

## failure_steps.csv

The first step that departs from what the question asks and explains the miss, for 144 failed runs (12 per model, drawn
at random from the wrong runs on computable and recognition questions, at most one per model and question).

| Step | Code | The run |
|---|---|---|
| Data | `source` | uses data that cannot answer the question, such as a coarse land-cover map, a wrong product, or misses data in the record |
| Data | `sensor` | joins sensors or products without making them consistent |
| Data | `prep` | gets the extent, projection or resampling wrong, or relies on flawed scenes |
| Time sampling | `sampling` | fills gaps such as the polar night by assumption, or rests on few or seasonally uneven scenes |
| Question | `definition` | computes a different quantity, such as winter as December to February |
| Analysis | `mapping` | maps change from the imagery with a different result |
| Analysis | `interpretation` | judges the type or cause of a change wrongly |
| Analysis | `statistics` | reaches its conclusion through the choice of test or quality filter |
| Close call | `margin` | uses a sound method whose result lies at a decision boundary |
| Unfinished | `incomplete` | gives no answer, or one it says it could not compute |
| Other | `report` | reports a conclusion that its own numbers contradict |
| Other | `unclear` | the cause is not visible in the report |

`uncertain` marks codes the coder was unsure of.

## sensor_reports.csv

What the method summary and caveats of each run say about the sensors, for the 228 wrong runs in instrument-pair cases
that move and the 45 runs in cases that hold beyond both.

| Report | The run |
|---|---|
| `attributed_to_instrument` | attributes a break in the altered period to the instrument |
| `break_not_attributed` | reports the break or a divergence from a concurrent satellite, but reads it as land change or leaves its cause open |
| `reported_separately` | reports the altered and a concurrent satellite separately, with different results, without flagging them |
| `generic_caveat` | gives only a generic caveat about sensors |
| `no_mention` | says nothing about them |

At the two sites with a real fire in the question period, reporting the drop caused by the fire answers the question and
does not count as noticing the alteration.
