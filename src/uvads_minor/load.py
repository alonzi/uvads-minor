"""Load the DS-minor snapshot and strip direct identifiers.

Raw data lives in data/raw/ (git-ignored, read-only). Nothing here writes back to it.
"""
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"

# Direct identifiers: never plotted, never written to processed outputs.
PII_COLS = [
    "UNIVERSITY_COMPUTING_ID",
    "PREFERRED_LAST_NAME",
    "PREFERRED_FIRST_NAME",
    "ADVISORS_NAME",
    "ADVISORS_EMAIL_ADDRESS",
]


def latest_snapshot() -> Path:
    files = sorted(RAW.glob("*_ds_minor_snapshot.csv"))
    if not files:
        raise FileNotFoundError(f"No snapshot CSV in {RAW}")
    return files[-1]


def load(path: Path | None = None, drop_pii: bool = True) -> pd.DataFrame:
    path = path or latest_snapshot()
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["CURRENT_PROGRAM_ACTION_DATE"] = pd.to_datetime(df["CURRENT_PROGRAM_ACTION_DATE"])
    if drop_pii:
        df = df.drop(columns=[c for c in PII_COLS if c in df.columns])
    return df
