"""Phase 1d: check OpenAlex data quality on a small sample of arXiv papers.

Samples papers from a few arXiv categories and years (via the arXiv API),
looks them up in OpenAlex by arXiv DOI, and measures coverage, date
agreement, counts_by_year consistency and citation levels per group.
Exploration only.
Usage: uv run scripts/sample_check.py
"""
import os
import random
import re
import time
from datetime import date, timedelta
from pathlib import Path

import feedparser
import httpx
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

ARXIV_URL = "http://export.arxiv.org/api/query"
OPENALEX_URL = "https://api.openalex.org"
OUT_DIR = Path("data/explore")

CATEGORIES = ["cs.LG", "hep-th", "math.AG"]
YEARS = [2015, 2018, 2021]
PAPERS_PER_GROUP = 20
WINDOW_DAYS = 14  # sample from one random two-week window per (category, year)
MAX_K = 5  # cumulative citations tracked for years 0..MAX_K after publication
LAST_FULL_YEAR = date.today().year - 1  # the current year is incomplete
SEED = 0


# ---------- arXiv: build the sample ----------

def fetch_arxiv_window(category: str, start: date, end: date) -> list[dict]:
    """Return papers whose PRIMARY category is `category`, submitted in [start, end]."""
    query = (
        f"cat:{category} AND "
        f"submittedDate:[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"
    )
    response = httpx.get(
        ARXIV_URL,
        params={"search_query": query, "max_results": 2000},  # 2000 = API maximum per call
        timeout=60,
        follow_redirects=True,
    )
    response.raise_for_status()
    papers = []
    for entry in feedparser.parse(response.text).entries:
        if entry.arxiv_primary_category["term"] != category:
            continue  # cross-listed into this category, primary is elsewhere
        arxiv_id = re.sub(r"v\d+$", "", entry.id.split("/abs/")[-1])  # drop version
        papers.append({
            "arxiv_id": arxiv_id,
            "category": category,
            "arxiv_date": date.fromisoformat(entry.published[:10]),  # v1 date
        })
    return papers


def build_sample(rng: random.Random) -> list[dict]:
    sample = []
    for category in CATEGORIES:
        for year in YEARS:
            offset = rng.randrange(365 - WINDOW_DAYS)
            start = date(year, 1, 1) + timedelta(days=offset)
            end = start + timedelta(days=WINDOW_DAYS - 1)
            papers = fetch_arxiv_window(category, start, end)
            chosen = rng.sample(papers, min(PAPERS_PER_GROUP, len(papers)))
            print(f"{category} {year}: window {start}..{end}, "
                  f"{len(papers)} primary papers, sampled {len(chosen)}")
            sample.extend(chosen)
            time.sleep(3)  # arXiv asks for one request every 3 seconds
    return sample


# ---------- OpenAlex: look up the sample ----------

def arxiv_doi(arxiv_id: str) -> str:
    return f"https://doi.org/10.48550/arxiv.{arxiv_id}".lower()


def fetch_openalex_one(arxiv_id: str, api_key: str) -> dict | None:
    """Look up one paper by arXiv DOI. Unlike the doi: filter, this resolves
    the arXiv DOI even when the preprint was merged into a published record."""
    response = httpx.get(
        f"{OPENALEX_URL}/works/{arxiv_doi(arxiv_id)}",
        params={"select": "id,doi,publication_date,cited_by_count,counts_by_year",
                "api_key": api_key},
        timeout=60,
        follow_redirects=True,
    )
    if response.status_code == 404:
        return None  # genuinely not in OpenAlex
    response.raise_for_status()
    return response.json()


def describe(paper: dict, work: dict | None) -> dict:
    """Turn one (arXiv paper, OpenAlex work) pair into a row of measurements."""
    row = {**paper, "year": paper["arxiv_date"].year, "found": work is not None}
    if work is None:
        return row
    oa_date = date.fromisoformat(work["publication_date"])
    by_year = {c["year"]: c["cited_by_count"] for c in work["counts_by_year"]}
    pub_year = row["year"]
    row.update({
        "openalex_id": work["id"],
        "merged": (work["doi"] or "").lower() != arxiv_doi(paper["arxiv_id"]),
        "openalex_date": oa_date,
        "same_date": oa_date == paper["arxiv_date"],
        "same_year": oa_date.year == pub_year,
        "cited_by_count": work["cited_by_count"],
        "counts_by_year_sum": sum(by_year.values()),
        "early_citations": sum(n for y, n in by_year.items() if y < pub_year),
    })
    running = row["early_citations"]  # citations before year 0 still count as "up to year k"
    for k in range(MAX_K + 1):
        y = pub_year + k
        running += by_year.get(y, 0)
        row[f"c{k}"] = running if y <= LAST_FULL_YEAR else None
    return row


# ---------- summary ----------

def summarize(df: pd.DataFrame) -> pd.DataFrame:
    # Not-found rows lack these keys, which makes the columns mixed-type; fix the type.
    found = df[df["found"]].astype({"same_year": bool, "same_date": bool, "merged": bool})
    by_group = df.groupby(["category", "year"])
    found_by_group = found.groupby(["category", "year"])
    return pd.DataFrame({
        "n": by_group.size(),
        "found_%": 100 * by_group["found"].mean(),
        "merged_%": 100 * found_by_group["merged"].mean(),
        "same_year_%": 100 * found_by_group["same_year"].mean(),
        "same_date_%": 100 * found_by_group["same_date"].mean(),
        "cby_sum_ok_%": 100 * found_by_group.apply(
            lambda g: (g["counts_by_year_sum"] == g["cited_by_count"]).mean()),
        "has_early_%": 100 * found_by_group.apply(lambda g: (g["early_citations"] > 0).mean()),
        "zero_cites_%": 100 * found_by_group.apply(lambda g: (g["cited_by_count"] == 0).mean()),
        "median_cites": found_by_group["cited_by_count"].median(),
        "mean_cites": found_by_group["cited_by_count"].mean(),
    }).round(1)


def plot_curves(df: pd.DataFrame, out_path: Path) -> None:
    """Mean and median cumulative citations by years since publication."""
    cols = [f"c{k}" for k in range(MAX_K + 1)]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colors = dict(zip(CATEGORIES, ["tab:blue", "tab:orange", "tab:green"]))
    styles = dict(zip(YEARS, ["-", "--", ":"]))
    found = df[df["found"]]
    for (category, year), group in found.groupby(["category", "year"]):
        values = group[cols].astype(float)
        for ax, stat in zip(axes, ["mean", "median"]):
            ax.plot(range(MAX_K + 1), values.agg(stat), color=colors[category],
                    linestyle=styles[year], marker="o", label=f"{category} {year}")
    for ax, stat in zip(axes, ["mean", "median"]):
        ax.set_title(f"{stat} cumulative citations")
        ax.set_xlabel("years since publication (k)")
    axes[0].legend(fontsize=8)
    fig.savefig(out_path, dpi=120)


def main() -> None:
    load_dotenv()
    api_key = os.environ["OPENALEX_API_KEY"]
    rng = random.Random(SEED)

    sample = build_sample(rng)
    works = {p["arxiv_id"]: fetch_openalex_one(p["arxiv_id"], api_key) for p in sample}
    df = pd.DataFrame([describe(p, works[p["arxiv_id"]]) for p in sample])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "sample.csv", index=False)

    pd.set_option("display.width", 200)
    print()
    print(summarize(df))
    plot_curves(df, OUT_DIR / "sample_curves.png")
    print(f"\nsaved {OUT_DIR / 'sample.csv'} and {OUT_DIR / 'sample_curves.png'}")


if __name__ == "__main__":
    main()
