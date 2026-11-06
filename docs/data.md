# Data

`scripts/download_data.py` builds this layout from the [Hugging Face dataset](https://huggingface.co/datasets/haoranranranran/EarthRecord):

```
data/
  questions.jsonl      268 question versions
  references.jsonl     238 reference answers
  views/<view>/        the files an agent sees at /data: 56 site views and 30 instrument-pair views
```

## Views

A site view holds the record of one site: one directory per collection, a `core_area.geojson` with the area's boundary
and suggested UTM zone, and a `README.md` that the agent reads. The README describes every collection, its file naming,
grid and the conversions from stored values to physical units. Files are single-band Cloud Optimized GeoTIFFs cut from
the source scenes on their own grids; no scale factor, offset, mask, composite or index is applied.

| Collection | Content | From |
|---|---|---|
| `landsat-c2-l2` | Landsat 4-9 Collection 2 Level-2, with the scene metadata | 1984 |
| `sentinel-2-l2a` | Sentinel-2 Level-2A, at most one scene per month | 2019 |
| `modis-13Q1-061`, `modis-13A1-061` | MODIS vegetation indices, Terra and Aqua | 2000 |
| `modis-11A2-061` | MODIS land surface temperature, Terra and Aqua | 2000 |
| `modis-10A1-061` | MODIS snow cover, Terra and Aqua | 2000 |
| `VNP13A1`, `VNP21A2` | VIIRS vegetation indices and land surface temperature | 2012 |
| `era5-land-monthly` | ERA5-Land monthly means | 1991 |
| `static/` | MODIS land cover, ESA WorldCover, Copernicus DEM, administrative boundaries | |

The eight regional sites have no Landsat or Sentinel-2 data. An altered view is its site view with one satellite's
files replaced (22 instrument pairs: Terra NDVI, Terra snow or Landsat 8 scaled from 2018 onward, or Landsat 8 scenes
of 2013-2017 removed so that Landsat 7 remains); a placebo view leaves out 5% of the clear scenes at random.

## Questions

`questions.jsonl` has one line per question version.

| Field | Meaning |
|---|---|
| `id` | Question id. Altered and placebo versions keep the id of their original question. |
| `version` | `original`, `altered` or `placebo` |
| `pair` | The original question whose reference scores this version |
| `view` | The view the agent works on |
| `question` | Question text given to the agent |
| `location` | The site's bounding box, given instead of the record in the closed book |
| `fields` | Answer fields: `name`, `kind` (`choice`, `num`, `year`, `month`, `set`, `ci`), `options` and `desc` |
| `canary` | Canary string of the question |
| `site` | Site id |
| `class` | `computable`, `recognition` or `insufficient_evidence` |
| `task` | One of ten analysis tasks (Quantify, Date, Trend, Detect, Compare, Attribute, Anomaly and climate, Recovery, Season, Regional statistics) |
| `theme` | forest, greening, agriculture, water, urban, fire, snow, coast or regional |
| `site_role` | `famous`, `stable`, `obscure` or `regional` |
| `reference_source` | `method` (computed from record variables), `record_product`, `withheld_product` (needs a map from the imagery), `visual` or `observations` |
| `no_change_reference` | Whether the reference conclusion is no change |
| `period_years`, `landsat_sensors`, `difficulty` | Length of the period asked, Landsat sensors it spans, difficulty label |
| `alteration` | Altered and placebo versions: the altered satellite, and for scaled data the scale and shape |

The agent answers through a `submit` tool built from `fields`, plus `confidence` (0-100), `datasets_used`,
`method_summary` and `caveats`. Every field accepts `insufficient_evidence`.

## Reference answers

`references.jsonl` has one line per original question: `id`, `conclusion` and `fields`. Each field gives `reference`
and, where they apply, `range` (the accepted interval of a number), `abs_tol`, `accept` (accepted alternatives, such as
near-tied years), and `by_year` with `depends_on` (a reference that depends on the year the answer picked).

`conclusion` names the field that holds the conclusion, or a rule on numeric fields:

| Rule | Conclusion |
|---|---|
| `"<field>"` | the value of that field |
| `["sign", f]` | the sign of `f` (within its tolerance of zero) |
| `["sign_ratio", f]` | whether `f` is above or below 1 (within 0.05) |
| `["sign_diff", f, g]` | the sign of `f - g` |
| `["recovered", f]` | whether `f` (years to recover) is a number or not |

See [scoring.md](scoring.md) for how answers are scored.
