"""Summary deck: dashboard, home school, majors, and what the action date says about declarations.

Usage:  uv run python scripts/make_summary.py [--out reports/summary.pdf]

Writes reports/summary.pdf and reports/summary_dashboard.pdf (dashboard page only).
All numbers are computed from the snapshot, not hard-coded.
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uvads_minor.load import latest_snapshot, load  # noqa: E402
from uvads_minor.majors import FIELDS, majors, plan_table  # noqa: E402

W, H = 13.33, 7.5
INK, MUTED = "#1f2933", "#6b7280"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK,
                     "ytick.color": INK})
FIELD_COLORS = dict(zip(FIELDS, ["#2b6cb0", "#63b3ed", "#dd6b20", "#805ad5",
                                 "#38a169", "#d69e2e", "#e53e3e", "#718096"]))
SCHOOL_SHORT = {"Arts & Sciences Undergraduate": "Arts & Sciences",
                "Engineering Undergraduate": "Engineering",
                "Commerce Undergraduate": "Commerce",
                "Architecture Undergraduate": "Architecture",
                "Education Undergraduate": "Education"}
SCHOOL_COLORS = {"Arts & Sciences": "#2b6cb0", "Engineering": "#dd6b20", "Commerce": "#38a169",
                 "Architecture": "#805ad5", "Education": "#d69e2e"}


def slide(title, subtitle=None):
    fig = plt.figure(figsize=(W, H))
    fig.text(0.05, 0.93, title, fontsize=22, weight="bold", color=INK)
    if subtitle:
        fig.text(0.05, 0.885, subtitle, fontsize=12, color=MUTED)
    return fig


def footer(fig, src, n, extra=""):
    fig.text(0.05, 0.025, f"Source: {src}  ·  N = {n} students  ·  {extra}"
             "FERPA-protected — internal use", fontsize=8, color=MUTED)


def hbar(ax, counts, colors, err=False):
    y = np.arange(len(counts))
    ax.barh(y, counts.values, color=colors,
            xerr=np.sqrt(counts.values) if err else None,
            ecolor="0.35", capsize=2, error_kw={"lw": 0.8})
    ax.set_yticks(y, counts.index)
    ax.invert_yaxis()
    pad = counts.max() * 0.012
    for yi, v in zip(y, counts.values):
        ax.text(v + (np.sqrt(v) if err else 0) + pad, yi, str(int(v)), va="center",
                fontsize=9, color=MUTED)
    ax.set_xlabel("students")


def field_legend(ax, fields):
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=FIELD_COLORS[f], label=f) for f in fields],
              frameon=False, loc="lower right", fontsize=9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/summary.pdf")
    args = ap.parse_args()

    src = latest_snapshot()
    df = load(src)
    N = len(df)
    df["SCHOOL"] = df["CURRENT_PROGRAM_DESC"].map(SCHOOL_SHORT)
    df["APPLIED"] = df["DEGREE_CHECKOUT_STATUS"].notna()
    M = majors(df).merge(df[["SCHOOL", "ACADEMIC_YEAR"]], left_on="sid", right_index=True)
    P = plan_table(df)

    # ---- numbers ----
    disc = M["discipline"].value_counts()
    fields = M.drop_duplicates(["sid", "field"])["field"].value_counts()
    cs = disc.get("Computer Science", 0)
    computing = fields.get("Computing", 0)
    small = disc[disc <= 5]
    n_small_students = M[M["discipline"].isin(small.index)]["sid"].nunique()
    no_major = N - M["sid"].nunique()
    school = df["SCHOOL"].value_counts()
    early = df["ACADEMIC_YEAR"].isin(["First-Year", "Second-Year"])
    early_eng_com = (early & df["SCHOOL"].isin(["Engineering", "Commerce"])).sum()
    other_minor = P[P["is_minor"]]
    eng_bus = (other_minor["discipline"] == "Engineering Business").sum()
    non_comp_eng_frac = 1 - computing / N

    d = df["CURRENT_PROGRAM_ACTION_DATE"]
    applied_dates_ok = d[df["APPLIED"]].min()
    na = df[~df["APPLIED"]]
    yr2_eng = na[(na["ACADEMIC_YEAR"] == "Second-Year") & (na["SCHOOL"] == "Engineering")]
    sp = df[df["EXPECTED_GRADUATION_TERM_DESC"] == "2027 Spring"]
    late = sp["CURRENT_PROGRAM_ACTION_DATE"] >= applied_dates_ok
    sp27_app, sp27_app_late = sp["APPLIED"].sum(), (late & sp["APPLIED"]).sum()
    sp27_na, sp27_na_late = (~sp["APPLIED"]).sum(), (late & ~sp["APPLIED"]).sum()
    yr2_eng_spring = yr2_eng["CURRENT_PROGRAM_ACTION_DATE"].dt.month.between(3, 5).sum()

    pct = lambda k: f"{100 * k / N:.0f}%"
    takeaways = [
        ("Computer Science is a third of the minor.",
         f"{cs} students ({pct(cs)}) major in CS; with Computer Engineering, computing majors are "
         f"{computing} ({pct(computing)}). The other {100 * non_comp_eng_frac:.0f}% come from outside computing."),
        ("Next tier: Systems Eng, Economics, Commerce, Global Studies, Applied Stats.",
         " · ".join(f"{k} {v}" for k, v in disc.iloc[1:6].items()) + "."),
        ("Long tail of majors.",
         f"{len(disc)} distinct majors; {len(small)} of them have ≤5 minors each "
         f"({n_small_students} students). Humanities & Arts majors: {fields.get('Humanities & Arts', 0)}."),
        ("Early declarers are mostly Engineering and Commerce students.",
         f"{early_eng_com} of {early.sum()} 1st/2nd-year minors are in Engineering or Commerce. "
         f"Every minor but {no_major} (Echols Scholars) already has a declared major."),
        ("Minors stack with business minors in Engineering.",
         f"{eng_bus} hold the Engineering Business minor too; "
         f"{other_minor['sid'].nunique()} hold some other minor."),
        ("No declaration date in this file — only an upper bound.",
         "CURRENT_PROGRAM_ACTION_DATE is the latest change to the whole program record "
         "(major, school, graduation). Declaration ≤ this date."),
        ("To measure declarations: ask SIS for the DS-minor plan's declare/effective date, "
         "or diff snapshots.",
         "Per-plan records usually carry their own effective date; saving a snapshot weekly "
         "also gives new declarations as the difference."),
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out) as pdf:
        # ---- derived for dashboard ----
        share = school / N
        school_l = school[share >= 0.05].copy()
        lumped = school[share < 0.05]
        if len(lumped):
            school_l["Other"] = lumped.sum()
        other_note = ", ".join(f"{k} {v}" for k, v in lumped.items())
        grad_year = df["EXPECTED_GRADUATION_TERM_DESC"].str[:4].astype(int)
        classes = grad_year.value_counts().sort_index(ascending=False)

        # 1. Dashboard
        from matplotlib.patches import FancyBboxPatch

        CARD = "#f4f6f9"
        fig = plt.figure(figsize=(W, H))
        fig.patch.set_facecolor("white")

        def card(x, y, w, h, title=None):
            fig.patches.append(FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                transform=fig.transFigure, facecolor=CARD, edgecolor="none", zorder=-1))
            if title:
                fig.text(x + 0.015, y + h - 0.035, title.upper(), fontsize=9.5,
                         weight="bold", color=MUTED)

        fig.text(0.04, 0.935, "Data Science Minor", fontsize=24, weight="bold", color=INK)
        fig.text(0.04, 0.895, f"School of Data Science · UVA · snapshot {src.name[:10]} "
                 "(Fall 2026)", fontsize=11, color=MUTED)

        # Big number
        card(0.04, 0.47, 0.20, 0.38)
        fig.text(0.14, 0.665, f"{N}", fontsize=72, weight="bold", color="#2b6cb0",
                 ha="center", va="center")
        fig.text(0.14, 0.555, "current minors", fontsize=15, color=INK, ha="center")
        fig.text(0.14, 0.51, f"{len(disc)} majors · {df['SCHOOL'].nunique()} schools",
                 fontsize=10.5, color=MUTED, ha="center")

        # School pie
        card(0.26, 0.47, 0.34, 0.38, "Home school")
        pax = fig.add_axes([0.27, 0.50, 0.16, 0.30])
        pcol = [SCHOOL_COLORS.get(s, "#a0aec0") for s in school_l.index]
        pax.pie(school_l.values, colors=pcol, startangle=90, counterclock=False,
                wedgeprops={"edgecolor": CARD, "linewidth": 2, "width": 0.45})
        pax.set_aspect("equal")
        for i, (s, v) in enumerate(school_l.items()):
            yy = 0.755 - i * 0.062
            fig.patches.append(plt.Rectangle((0.45, yy - 0.012), 0.012, 0.024,
                                             color=pcol[i], transform=fig.transFigure))
            fig.text(0.468, yy, s, fontsize=10.5, va="center", color=INK, weight="bold")
            fig.text(0.468, yy - 0.026, f"{v} students · {100 * v / N:.0f}%", fontsize=9,
                     va="center", color=MUTED)
        if len(lumped):
            fig.text(0.45, 0.49, f"Other = {other_note}", fontsize=8, color=MUTED)

        # Graduating classes
        card(0.62, 0.47, 0.34, 0.38, "Minors by graduating class")
        cax = fig.add_axes([0.64, 0.555, 0.30, 0.22])
        cax.set_facecolor(CARD)
        x = np.arange(len(classes))
        cax.bar(x, classes.values, color="#2b6cb0", width=0.65)
        for xi, v in zip(x, classes.values):
            cax.text(xi, v + classes.max() * 0.03, str(v), ha="center", fontsize=10,
                     color=INK, weight="bold")
        cax.set_xticks(x, [f"'{str(c)[2:]}" for c in classes.index], fontsize=10)
        cax.set_yticks([])
        cax.spines[["left", "top", "right"]].set_visible(False)
        cax.set_ylim(0, classes.max() * 1.18)
        fig.text(0.635, 0.49, "Class = calendar year of expected graduation term",
                 fontsize=8, color=MUTED)

        # Top majors
        card(0.04, 0.06, 0.45, 0.37, "Top majors")
        top10 = disc.head(10)
        fmap_ = M.drop_duplicates("discipline").set_index("discipline")["field"]
        max_ = top10.max()
        for i, (d_, v) in enumerate(top10.items()):
            yy = 0.355 - i * 0.028
            label = f"{d_} (all)" if d_ == "Computer Science" else d_
            fig.text(0.055, yy, label, fontsize=9.5, va="center", color=INK)
            fig.patches.append(plt.Rectangle(
                (0.215, yy - 0.009), 0.23 * v / max_, 0.018, transform=fig.transFigure,
                color=FIELD_COLORS[fmap_[d_]]))
            fig.text(0.215 + 0.23 * v / max_ + 0.005, yy, str(v), fontsize=9,
                     va="center", color=MUTED)

        # Major fields
        card(0.51, 0.06, 0.45, 0.37, "Major fields")
        fmax = fields.max()
        for i, (f_, v) in enumerate(fields.items()):
            yy = 0.355 - i * 0.035
            fig.text(0.525, yy, f_, fontsize=9.5, va="center", color=INK)
            fig.patches.append(plt.Rectangle(
                (0.70, yy - 0.011), 0.20 * v / fmax, 0.022, transform=fig.transFigure,
                color=FIELD_COLORS[f_]))
            fig.text(0.70 + 0.20 * v / fmax + 0.005, yy, str(v), fontsize=9,
                     va="center", color=MUTED)
        fig.text(0.525, 0.075, "Double majors in two fields count in both", fontsize=8,
                 color=MUTED)

        fig.text(0.04, 0.025, f"Source: {src.name}  ·  FERPA-protected — internal use",
                 fontsize=8, color=MUTED)
        fig.savefig(out.with_name(out.stem + "_dashboard.pdf"))
        pdf.savefig(fig)
        plt.close(fig)

        # 2. School pie (same <5% lumping as dashboard)
        fig = slide("Which school minors come from",
                    "Raw counts — not normalized by school size"
                    + (f" · Other = {other_note}" if len(lumped) else ""))
        ax = fig.add_axes([0.08, 0.08, 0.55, 0.76])
        ax.pie(school_l.values, colors=pcol, startangle=90, counterclock=False,
               wedgeprops={"edgecolor": "white", "linewidth": 1.5},
               autopct=lambda p: f"{p:.0f}%" if p >= 3 else "", pctdistance=0.72,
               textprops={"color": "white", "weight": "bold", "fontsize": 12})
        ax.set_aspect("equal")
        lax = fig.add_axes([0.62, 0.30, 0.3, 0.4])
        lax.axis("off")
        for i, (s, v) in enumerate(school_l.items()):
            lax.add_patch(plt.Rectangle((0, 0.85 - i * 0.18), 0.06, 0.1,
                                        color=pcol[i], transform=lax.transAxes))
            lax.text(0.1, 0.9 - i * 0.18, f"{s}", fontsize=14, va="center", color=INK,
                     transform=lax.transAxes)
            lax.text(0.85, 0.9 - i * 0.18, f"{v}  ({100 * v / N:.1f}%)", fontsize=12,
                     va="center", ha="right", color=MUTED, transform=lax.transAxes)
        footer(fig, src.name, N)
        pdf.savefig(fig)
        plt.close(fig)

        # 3. Majors (disciplines)
        top = disc.head(25)
        fmap = M.drop_duplicates("discipline").set_index("discipline")["field"]
        fig = slide("Majors of DS minors",
                    f"Top 25 of {len(disc)} majors · BA/BS/second-major collapsed · "
                    "double majors count in each")
        ax = fig.add_axes([0.24, 0.11, 0.72, 0.74])
        hbar(ax, top, [FIELD_COLORS[fmap[d_]] for d_ in top.index])
        field_legend(ax, [f for f in FIELDS if f in set(fmap[top.index])])
        footer(fig, src.name, N)
        pdf.savefig(fig)
        plt.close(fig)

        # 4. Fields
        fig = slide("Majors grouped by field",
                    "Students counted once per field; a double major in two fields counts in both")
        ax = fig.add_axes([0.24, 0.12, 0.66, 0.70])
        hbar(ax, fields, [FIELD_COLORS[f] for f in fields.index])
        footer(fig, src.name, N)
        pdf.savefig(fig)
        plt.close(fig)

        # 5. What is CURRENT_PROGRAM_ACTION_DATE?
        fig = slide("What CURRENT_PROGRAM_ACTION_DATE measures",
                    "Latest change to the program record — an upper bound on the declaration date")
        ax = fig.add_axes([0.06, 0.40, 0.55, 0.43])
        month = na["CURRENT_PROGRAM_ACTION_DATE"].dt.to_period("M")
        rng = pd.period_range(month.min(), month.max(), freq="M")
        ct = pd.crosstab(month, na["SCHOOL"]).reindex(rng, fill_value=0)
        ct = ct[[s for s in school.index if s in ct.columns]]
        bottom = np.zeros(len(rng))
        x = np.arange(len(rng))
        for s in ct.columns:
            ax.bar(x, ct[s].values, bottom=bottom, color=SCHOOL_COLORS[s], label=s)
            bottom += ct[s].values
        ax.set_xticks(x, [p.strftime("%b\n%y") if p.month in (4, 11) else "" for p in rng],
                      fontsize=8)
        ax.set_ylabel("students")
        ax.set_title(f"Month of last action — students who have not applied to graduate "
                     f"(n={len(na)})", loc="left", fontsize=11)
        ax.legend(frameon=False, fontsize=8, loc="upper left")

        ax2 = fig.add_axes([0.06, 0.08, 0.55, 0.22])
        dd = d.sort_values()
        ax2.step(dd.values, np.arange(1, N + 1), where="post", color="#2b6cb0")
        ax2.set_ylabel("cumulative")
        ax2.set_title("Lower bound on current minors declared by date t:  #{action date ≤ t}",
                      loc="left", fontsize=11)
        ax2.tick_params(axis="x", labelsize=8)
        import matplotlib.dates as mdates
        ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(4, 11)))
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

        evidence = [
            ("b", "Why it is not the minor declaration date"),
            ("", "• Applying to graduate resets the date. Compare"),
            ("", "   students in the same class (expected Spring '27):"),
            ("", f"   applied: {sp27_app_late}/{sp27_app} dated ≥ {applied_dates_ok:%b %d %Y}"),
            ("", f"   not applied: {sp27_na_late}/{sp27_na} dated ≥ {applied_dates_ok:%b %d %Y}"),
            ("", "   So the application replaced the earlier date"),
            ("", "   (possibly the declaration), which is now lost."),
            ("", f"• {yr2_eng_spring} of {len(yr2_eng)} Engineering 2nd-years are dated"),
            ("", "   spring 2026 = end-of-1st-year major declaration."),
            ("", "• Spikes in early April and early November,"),
            ("", "   when records get edited around registration."),
            ("", "• No date predates the student's matriculation."),
            ("", ""),
            ("b", "So: declaration date ≤ action date"),
            ("", ""),
            ("b", "To get the real date"),
            ("", "• Ask the registrar/SIS for the DS-minor plan's"),
            ("", "   own declare/effective date."),
            ("", "• Or save a snapshot weekly: new IDs between"),
            ("", "   snapshots = new declarations."),
        ]
        for i, (w, line) in enumerate(evidence):
            fig.text(0.655, 0.82 - i * 0.042, line, fontsize=10, color=INK,
                     weight="bold" if w else "normal")
        footer(fig, src.name, N)
        pdf.savefig(fig)
        plt.close(fig)

    print(f"wrote {out}")
    for i, (h, b) in enumerate(takeaways, 1):
        print(i, h, "|", b)


if __name__ == "__main__":
    main()
