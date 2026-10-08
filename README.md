# Newton's Laws Lab — Vernier `.gambl` data pipeline

Python scripts that read **Vernier Graphical Analysis** (`.gambl`) files from an AP Physics 1
dynamics-cart lab and turn them into CSV tables, PNG graphs and a slide deck that cover
Newton's 1st, 2nd and 3rd Laws plus an inclined-ramp run.

## How a `.gambl` file is put together

- It is a **tar archive** containing `vstudm/manifest.json` and `vstudm/data.udm`.
- `data.udm` is **XML**. Each run is a `<DataSet>`; each measurement is a `<DataColumn>` with a
  name (`Position G`), units (`m`) and newline-separated values in `<ColumnCells>`.
- A cell of `Z1 1:` means the sensor missed that sample — it is read as a blank.
- Every save keeps all earlier runs of the session, so the last file holds every run. Each run is
  attributed to the first file it appeared in.

The reader is ~20 lines — see `read_runs()` in [`src/export_gambl.py`](src/export_gambl.py).

## Scripts (`src/`)

| Script | What it does |
|---|---|
| `export_gambl.py` | `read_runs()` + raw export of every run (summary table + graph per run) |
| `build_n2l.py` | **N2L** — launch acceleration (slope of v-t during a plunger push) vs. mass; a vs 1/m fit |
| `build_n1l.py` | **N1L** — coasting at ~constant velocity + inertia; writes all CSV tables |
| `build_n3l.py` | **N3L** — collision impulses (m·Δv) and contact forces (m·a) on both cars |
| `build_angled.py` | **Ramp** — constant acceleration; ramp angle and friction from up vs. down rolls |
| `build_slides.py` | Condensed per-trial tables and a `.pptx` deck (graph + table per trial, summary per law) |
| `run_all.py` | Runs the whole pipeline |

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# copy your .gambl files into data/ (see data/README.md), then:
python src/run_all.py            # outputs/ gets CSVs, PNGs and the slide deck
```

`GAMBL_DIR` and `OUT_DIR` environment variables override the input and output folders.

## Lab-specific assumptions

These are hard-coded for this lab session — change them for other data:

- Cart = 0.292 kg; each added weight = 0.142 kg.
- Sensor **G** (green trace) = **Car 1**, sensor **Y** (yellow trace) = **Car 2**.
- N2L trials `N2L_1`…`N2L_5` = 0…4 weights on Car 1, using the cleanest launch in each file (`TRIALS` in `build_n2l.py`).
- N3L weights per car were **inferred** from each collision's velocity-change ratio and cross-checked
  against peak contact forces (`RUNS` in `build_n3l.py`). Inferring masses from the same data used to
  test N3L is partly circular — confirm against lab notes.
- Thresholds (what counts as "moving", "launch", "contact", "free roll") are named constants at the top of each script.
