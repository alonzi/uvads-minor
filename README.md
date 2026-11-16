# uvads-minor

Analysis of the UVA School of Data Science undergraduate minor.

**This repo holds code only.** Student data is FERPA-protected and must never be
committed — `.gitignore` blocks `data/`, `reports/`, `*.csv`, `*.pdf`.

## Setup

```bash
git clone https://github.com/alonzi/uvads-minor.git ~/uvads-minor
cd ~/uvads-minor
uv sync                      # creates .venv and uv.lock — commit uv.lock afterwards
mkdir -p data/raw
cp <path>/YYYY-MM-DD-..._ds_minor_snapshot.csv data/raw/
chmod 444 data/raw/*.csv     # raw data is read-only
```

## Run

```bash
uv run python scripts/make_summary.py      # reports/summary.pdf + reports/summary_dashboard.pdf
uv run python scripts/make_histograms.py   # reports/histograms.pdf (every 1D and 2D histogram)
```

Scripts use the newest `data/raw/*_ds_minor_snapshot.csv`.

## Layout

```
src/uvads_minor/load.py     load snapshot, drop direct identifiers
src/uvads_minor/majors.py   parse NON_DS_PLANS -> majors, map to fields
scripts/                    report generators
data/        (ignored)      raw/ and processed/ snapshots
reports/     (ignored)      generated PDFs
```

## Notes

- `CURRENT_PROGRAM_ACTION_DATE` is the latest change to the student's program record,
  not the minor declaration date. Declaration date ≤ action date.
- Major→field mapping in `majors.py` is hand-built; edit `FIELDS` to regroup.
