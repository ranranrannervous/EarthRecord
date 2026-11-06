# Scoring

The code is [earthrecord/scoring.py](../earthrecord/scoring.py) (single runs) and
[earthrecord/analysis.py](../earthrecord/analysis.py) (tables).

## A run

A run is **right** when its conclusion field earns full credit. Where the conclusion is decided by the sign of a number
(`sign`, `sign_ratio`, `sign_diff`), that number must also lie inside its reference range.

Field scores, from 0 to 1:

| Kind | Score |
|---|---|
| `choice` | 1 for the reference or an accepted alternative |
| `year` | 1 for an accepted year, 0.5 for one year off |
| `month` | 1 for an accepted month, 0.5 for one month off (December and January are adjacent) |
| `set` | F1 score over years, a year matching when within one year of a reference year |
| `num` | 1 inside the reference range plus the absolute tolerance; outside it, the mean relative accuracy of the distance to the nearest bound over thresholds 0.50 to 0.95 |
| any | `insufficient_evidence` earns 1 only where it is the reference |

The question score gives the conclusion half of the weight and shares the other half among the remaining fields; a wrong
conclusion sets it to 0. It is reported in the logs for completeness; the paper uses right and pass^3.

A run **abstains** when it answers `insufficient_evidence` for the conclusion of a question whose reference is not
insufficient evidence. On the 12 insufficient-evidence questions, answering `insufficient_evidence` is the right answer.

## A question

**pass^3**: the question counts when all three passes are right. Scores are percentages of questions; the main results
use the 226 computable and recognition questions with the record. Intervals are 95% bootstrap intervals over questions
(2,000 resamples).

**Confidence**: AUROC of the reported confidence for right against wrong runs, over the runs that answer.

## Instrument pairs

A model-pair case is *right on the original* when the original question is right in all three passes with the record.
It then

- **moves** when the altered version is not right in all three passes;
- is **held** when it stays right and the question is right in the closed book or has no change as its reference;
- holds **beyond** both otherwise.

Placebo pairs are classified the same way and measure how often answers change for reasons unrelated to an instrument.

## Baselines

- **Majority class**: for each question, the most common reference conclusion among the other questions with the same
  answer type (ties go to the class met first in `references.jsonl`); numeric conclusions have no class and count as wrong.
- **Always no change**: the no-change option wherever the conclusion offers one.
