"""1D histogram of every variable + 2D histogram of every unique pair -> one PDF.

Usage:  uv run python scripts/make_histograms.py [--out reports/histograms.pdf]

Every variable is mapped to an ordered set of bins (categories, months, FTE steps)
so that 1D and 2D plots share one code path. Missing values get an explicit
"(missing)" bin -- nothing is silently dropped.
"""
import argparse
import itertools
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uvads_minor.load import PII_COLS, latest_snapshot, load  # noqa: E402

MISSING = "(missing)"
TOP_N = 15  # high-cardinality categoricals: keep top N, lump rest into "Other"

ORDERS = {
    "ACADEMIC_YEAR": ["First-Year", "Second-Year", "Third-Year", "Fourth-Year"],
}


def term_key(s: str):
    """'2027 Spring' -> sortable (2027, 0)."""
    yr, sem = s.split()
    return (int(yr), {"Spring": 0, "Summer": 1, "Fall": 2}.get(sem, 3))


def binned(df: pd.DataFrame) -> dict[str, pd.Categorical]:
    out = {}
    for col in df.columns:
        s = df[col]
        if col == "CURRENT_PROGRAM_ACTION_DATE":
            p = s.dt.to_period("M")
            cats = pd.period_range(p.min(), p.max(), freq="M").astype(str).tolist()
            vals = p.astype(str)
        elif col == "FTE":
            # FTE is credits/15 -> discrete in steps of 1/30; bin on that grid
            k = np.round(s * 30).astype(int)
            grid = range(k.min(), k.max() + 1)
            cats = [f"{i / 30:.3f}" for i in grid]
            vals = (k / 30).map(lambda x: f"{x:.3f}")
        else:
            vals = s.astype("object")
            counts = vals.value_counts()
            if col in ORDERS:
                cats = [c for c in ORDERS[col] if c in counts.index]
            elif col.endswith("TERM_DESC"):
                cats = sorted(counts.index, key=term_key)
            elif len(counts) > TOP_N:
                keep = counts.index[:TOP_N].tolist()
                vals = vals.where(vals.isin(keep) | vals.isna(), "Other")
                cats = keep + ["Other"]
            else:
                cats = counts.index.tolist()
        vals = pd.Series(vals, index=s.index).where(s.notna(), MISSING)
        if (vals == MISSING).any():
            cats = cats + [MISSING]
        out[col] = pd.Categorical(vals, categories=cats, ordered=True)
    return out


def short(label: str, n: int = 38) -> str:
    return label if len(label) <= n else label[: n - 1] + "…"


def plot_1d(ax, col, cat):
    counts = pd.Series(cat).value_counts(sort=False).reindex(cat.categories, fill_value=0)
    y = np.arange(len(counts))
    ax.barh(y, counts.values, xerr=np.sqrt(counts.values), color="#4C72B0",
            ecolor="0.3", capsize=2, error_kw={"lw": 0.8})
    ax.set_yticks(y, [short(str(c)) for c in counts.index], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("students  (error bars: √N)", fontsize=8)
    ax.set_title(f"{col}   [N={counts.sum()}, {len(counts)} bins]", fontsize=9)
    ax.tick_params(axis="x", labelsize=7)


def plot_2d(fig, cx, x, cy, y):
    tab = pd.crosstab(pd.Series(y, name=cy), pd.Series(x, name=cx), dropna=False)
    tab = tab.reindex(index=y.categories, columns=x.categories, fill_value=0)
    ax = fig.add_subplot(111)
    data = np.ma.masked_equal(tab.values, 0)
    im = ax.imshow(data, aspect="auto", cmap="viridis", interpolation="nearest")
    ax.set_xticks(range(tab.shape[1]), [short(str(c), 24) for c in tab.columns],
                  rotation=60, ha="right", fontsize=6)
    ax.set_yticks(range(tab.shape[0]), [short(str(c), 30) for c in tab.index], fontsize=6)
    ax.set_xlabel(cx, fontsize=9)
    ax.set_ylabel(cy, fontsize=9)
    ax.set_title(f"{cy}  vs  {cx}   [N={int(tab.values.sum())}; empty cells blank]", fontsize=10)
    if tab.size <= 500:
        vmax = data.max() if data.count() else 1
        for (i, j), v in np.ndenumerate(tab.values):
            if v:
                ax.text(j, i, str(v), ha="center", va="center", fontsize=5,
                        color="black" if v > 0.6 * vmax else "white")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01, label="students")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/histograms.pdf")
    args = ap.parse_args()

    src = latest_snapshot()
    df = load(src)
    B = binned(df)
    cols = list(B)
    pairs = list(itertools.combinations(cols, 2))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out) as pdf:
        # title page
        fig = plt.figure(figsize=(11, 8.5))
        fig.text(0.06, 0.92, "DS Minor snapshot — 1D and 2D histograms", fontsize=18, weight="bold")
        notes = [
            f"Source: {src.name}   ({len(df)} students)",
            f"Variables plotted ({len(cols)}): " + ", ".join(cols),
            f"Excluded as direct identifiers: {', '.join(PII_COLS)}",
            f"Pages: {len(cols)} 1D histograms (4/page), then {len(pairs)} 2D histograms "
            "(upper triangle, no diagonal; one per page).",
            "Binning: categoricals as-is (top 15 + 'Other' when >15 levels); "
            "CURRENT_PROGRAM_ACTION_DATE by month; FTE on its native 1/30 grid.",
            "Missing values shown as an explicit '(missing)' bin.",
            "Constant columns (TERM_DESC, ACADEMIC_PLAN_DESC) and the duplicate pair "
            "CURRENT_PROGRAM_DESC == ACADEMIC_PROGRAM_DESC are kept for completeness.",
            "Contains small-count cells — treat as FERPA-protected; do not post publicly.",
        ]
        for i, line in enumerate(notes):
            fig.text(0.06, 0.82 - i * 0.07, line, fontsize=10, wrap=True)
        pdf.savefig(fig)
        plt.close(fig)

        for page in range(0, len(cols), 4):
            fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
            for ax, col in itertools.zip_longest(axes.flat, cols[page:page + 4]):
                if col is None:
                    ax.axis("off")
                else:
                    plot_1d(ax, col, B[col])
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

        for cx, cy in pairs:
            fig = plt.figure(figsize=(11, 8.5))
            plot_2d(fig, cx, B[cx], cy, B[cy])
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    print(f"wrote {out}  ({1 + -(-len(cols) // 4) + len(pairs)} pages)")


if __name__ == "__main__":
    main()
