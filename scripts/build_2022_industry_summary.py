"""Build a compact county-by-industry summary from 2022_occind.dta."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SOURCE_COLUMNS = [
    "fips_concat",
    "ind1990",
    "employed_workers",
    "employed_STARs",
]
GROUP_COLUMNS = ["county_fips", "industry"]
VALUE_COLUMNS = ["employed_workers", "employed_noncollege"]


def normalize_county_fips(series: pd.Series) -> pd.Series:
    """Return county identifiers as zero-padded five-character strings."""
    normalized = series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    return normalized.str.zfill(5)


def aggregate_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Collapse occupation rows in one source chunk to county industries."""
    prepared = chunk.rename(
        columns={
            "fips_concat": "county_fips",
            "ind1990": "industry",
            "employed_STARs": "employed_noncollege",
        }
    ).copy()
    prepared["county_fips"] = normalize_county_fips(prepared["county_fips"])
    prepared["industry"] = prepared["industry"].astype("string").str.strip()
    prepared = prepared.dropna(subset=GROUP_COLUMNS)
    prepared = prepared[prepared["industry"].ne("")]
    return (
        prepared.groupby(GROUP_COLUMNS, as_index=False, observed=True)[VALUE_COLUMNS]
        .sum()
    )


def validate_summary(summary: pd.DataFrame) -> None:
    """Raise ValueError when the generated summary violates core invariants."""
    if summary[GROUP_COLUMNS].isna().any().any():
        raise ValueError("Summary contains missing county or industry identifiers")
    if summary.duplicated(GROUP_COLUMNS).any():
        raise ValueError("Summary contains duplicate county-industry rows")
    if (summary[VALUE_COLUMNS] < 0).any().any():
        raise ValueError("Summary contains negative employment estimates")
    if (summary["employed_noncollege"] > summary["employed_workers"] + 1e-6).any():
        raise ValueError("Non-college employment exceeds total employment")


def build_summary(source: Path, output: Path, chunksize: int = 250_000) -> pd.DataFrame:
    """Stream the Stata source, aggregate it, validate it, and write gzip CSV."""
    partials = []
    reader = pd.read_stata(
        source,
        columns=SOURCE_COLUMNS,
        iterator=True,
        chunksize=chunksize,
    )
    for chunk in reader:
        partials.append(aggregate_chunk(chunk))

    summary = (
        pd.concat(partials, ignore_index=True)
        .groupby(GROUP_COLUMNS, as_index=False, observed=True)[VALUE_COLUMNS]
        .sum()
        .sort_values(GROUP_COLUMNS, kind="stable")
        .reset_index(drop=True)
    )
    validate_summary(summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output, index=False, compression="gzip")
    return summary


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "data" / "2022_occind.dta")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "data" / "2022_industry_county_summary.csv.gz",
    )
    parser.add_argument("--chunksize", type=int, default=250_000)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = build_summary(arguments.source, arguments.output, arguments.chunksize)
    print(f"Wrote {len(result):,} county-industry rows to {arguments.output}")
