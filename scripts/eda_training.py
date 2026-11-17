"""Exploratory plots on the training cohorts (year 0 = 2012-2016) only.

The 2017 test cohort is never loaded, so nothing seen here can influence
modelling choices. Figures are written to figures/.
"""
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np

DATASET = "data/dataset.parquet"
OUT = Path("figures")
FIRST, LAST = 2012, 2016       # training cohorts of the paper-style split
MAX_AGE = 9                    # 2016 + 9 = 2025: observed for every cohort
ML = ("cs.LG", "cs.CL", "cs.AI")

cols = ", ".join(f"cit_y{i}" for i in range(MAX_AGE + 1))
df = duckdb.sql(f"""
    SELECT CASE WHEN primary_category IN {ML} THEN 'ML (cs.LG/CL/AI)'
                ELSE primary_archive END AS area,
           CASE WHEN primary_category IN {ML} THEN 'ML (cs.LG/CL/AI)'
                WHEN primary_archive = 'cs'    THEN 'CS (other)'
                WHEN primary_archive = 'math'  THEN 'Math'
                WHEN primary_archive = 'stat'  THEN 'Statistics'
                WHEN primary_archive = 'q-bio' THEN 'Quant. biology'
                WHEN primary_archive = 'q-fin' THEN 'Quant. finance'
                WHEN primary_archive = 'eess'  THEN 'EESS'
                WHEN primary_archive = 'econ'  THEN 'Economics'
                ELSE 'Physics' END AS grp,      -- every other archive is physics
           {cols}
    FROM '{DATASET}'
    WHERE exclude_reason IS NULL AND has_record
      AND year0 BETWEEN {FIRST} AND {LAST}
""").df()

yearly = df[[f"cit_y{i}" for i in range(MAX_AGE + 1)]].to_numpy()
cum = yearly.cumsum(axis=1)                # cum[:, i] = citations through year i
is_ml = (df["area"] == "ML (cs.LG/CL/AI)").to_numpy()
groups = df["grp"].value_counts().index          # all 9 arXiv groups, largest first
print(f"{len(df):,} papers, {is_ml.sum():,} ML")

OUT.mkdir(exist_ok=True)

# 1. Tail: share of papers with at least x citations through year 3.
fig, ax = plt.subplots(figsize=(6, 4.5))
for name, mask in [("ML", is_ml), ("all other", ~is_ml)]:
    x = np.sort(cum[mask, 3])
    share = 1 - np.arange(len(x)) / len(x)       # P(X >= x)
    pos = x > 0
    ax.loglog(x[pos], share[pos], label=f"{name} ({(x == 0).mean():.0%} have 0)")
ax.set(xlabel="citations through year 3", ylabel="share of papers with at least x",
       title="Heavy tail of early citations (2012-2016 cohorts)")
ax.legend()
fig.savefig(OUT / "tail_year3.png", dpi=150, bbox_inches="tight")

# 2. Curves: level (mean total) and timing (scaled to year 9).
def plot_curves(column, names, title, path):
    """Mean cumulative citations by age (level) and scaled to year 9 (timing)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ages = np.arange(MAX_AGE + 1)
    for name in names:
        m = cum[(df[column] == name).to_numpy()].mean(axis=0)
        style = dict(lw=2.5, color="black") if name.startswith("ML") else {}
        a1.plot(ages, m, label=name, **style)
        a2.plot(ages, m / m[-1], **style)
    a1.set(xlabel="years since year 0", ylabel="mean citations so far", title="Level")
    a2.set(xlabel="years since year 0", ylabel="share of year-9 total", title="Timing")
    a1.legend(fontsize=8)
    fig.suptitle(title)
    fig.savefig(OUT / path, dpi=150, bbox_inches="tight")


plot_curves("grp", groups, "arXiv groups", "curves_by_group.png")

# Check: do physics archives differ as much as groups do?
physics = df.loc[df["grp"] == "Physics", "area"].value_counts().index
plot_curves("area", physics, "Physics archives only", "curves_physics.png")

# 3. Share of uncited papers at years 0-3, by group.
fig, ax = plt.subplots(figsize=(10, 4.5))
width = 0.2
for k in range(4):
    zero = [(cum[(df["grp"] == g).to_numpy(), k] == 0).mean() for g in groups]
    ax.bar(np.arange(len(groups)) + k * width, zero, width, label=f"through year {k}")
ax.set_xticks(np.arange(len(groups)) + 1.5 * width, groups, rotation=30, ha="right")
ax.set(ylabel="share with 0 citations", title="Uncited papers by arXiv group")
ax.legend()
fig.savefig(OUT / "zero_share.png", dpi=150, bbox_inches="tight")

# 4. Persistence: citations through year 1 vs through year 4.
fig, ax = plt.subplots(figsize=(5.5, 5))
hb = ax.hexbin(np.log1p(cum[:, 1]), np.log1p(cum[:, 4]), gridsize=40, bins="log")
fig.colorbar(hb, label="papers (log)")
ticks = [0, 1, 10, 100, 1000]
ax.set_xticks(np.log1p(ticks), ticks)
ax.set_yticks(np.log1p(ticks), ticks)
ax.set(xlabel="citations through year 1", ylabel="citations through year 4",
       title="How much year 1 tells about year 4")
fig.savefig(OUT / "persistence.png", dpi=150, bbox_inches="tight")

rank_corr = np.corrcoef(*(np.argsort(np.argsort(cum[:, i])) for i in (1, 4)))[0, 1]
print(f"rank correlation, through year 1 vs through year 4: {rank_corr:.2f}")
