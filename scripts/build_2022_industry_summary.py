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
OCCUPATION_SOURCE_COLUMNS = [
    "fips_concat",
    "occsoc",
    "occ2010",
    "ind1990",
    "employed_workers",
    "employed_STARs",
]
OCCUPATION_GROUP_COLUMNS = ["county_fips", "occupation_code", "occupation"]


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


def aggregate_occupation_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Collapse a source chunk to county, occupation, and industry."""
    prepared = chunk.rename(
        columns={
            "fips_concat": "county_fips",
            "occsoc": "occupation_code",
            "occ2010": "occupation",
            "ind1990": "industry",
            "employed_STARs": "employed_noncollege",
        }
    ).copy()
    prepared["county_fips"] = normalize_county_fips(prepared["county_fips"])
    for column in ["occupation_code", "occupation", "industry"]:
        prepared[column] = prepared[column].astype("string").str.strip()
    group_columns = OCCUPATION_GROUP_COLUMNS + ["industry"]
    prepared = prepared.dropna(subset=group_columns)
    for column in ["occupation_code", "occupation", "industry"]:
        prepared = prepared[prepared[column].ne("")]
    return (
        prepared.groupby(group_columns, as_index=False, observed=True)[VALUE_COLUMNS]
        .sum()
    )


def select_common_industries(
    occupation_industries: pd.DataFrame, limit: int = 3
) -> pd.DataFrame:
    """Return the leading industries for each county occupation."""
    eligible = occupation_industries[
        occupation_industries["employed_noncollege"].gt(0)
    ].copy()
    eligible = eligible.sort_values(
        OCCUPATION_GROUP_COLUMNS
        + ["employed_noncollege", "employed_workers", "industry"],
        ascending=[True, True, True, False, False, True],
        kind="stable",
    )
    leading = eligible.groupby(
        OCCUPATION_GROUP_COLUMNS, as_index=False, observed=True
    ).head(limit)
    return (
        leading.groupby(OCCUPATION_GROUP_COLUMNS, as_index=False, observed=True)[
            "industry"
        ]
        .agg(lambda values: " · ".join(values.astype(str)))
        .rename(columns={"industry": "common_industries"})
    )


def validate_occupation_summary(summary: pd.DataFrame) -> None:
    """Validate the compact county-by-occupation output."""
    required = OCCUPATION_GROUP_COLUMNS + VALUE_COLUMNS + ["common_industries"]
    if summary[required].isna().any().any():
        raise ValueError("Occupation summary contains missing required values")
    if summary.duplicated(["county_fips", "occupation_code"]).any():
        raise ValueError("Occupation summary contains duplicate county occupations")
    if (summary[VALUE_COLUMNS] < 0).any().any():
        raise ValueError("Occupation summary contains negative employment estimates")
    if (summary["employed_noncollege"] > summary["employed_workers"] + 1e-6).any():
        raise ValueError("Occupation non-college employment exceeds total employment")


def build_occupation_summary(
    source: Path, output: Path, chunksize: int = 250_000
) -> pd.DataFrame:
    """Build and write the county-by-occupation summary and common industries."""
    totals = []
    industry_candidates = []
    reader = pd.read_stata(
        source,
        columns=OCCUPATION_SOURCE_COLUMNS,
        iterator=True,
        chunksize=chunksize,
    )
    for chunk in reader:
        detailed = aggregate_occupation_chunk(chunk)
        totals.append(
            detailed.groupby(
                OCCUPATION_GROUP_COLUMNS, as_index=False, observed=True
            )[VALUE_COLUMNS].sum()
        )
        ranked = detailed.sort_values(
                OCCUPATION_GROUP_COLUMNS
                + ["employed_noncollege", "employed_workers"],
                ascending=[True, True, True, False, False],
                kind="stable",
            )
        candidates = ranked.groupby(
            OCCUPATION_GROUP_COLUMNS, as_index=False, observed=True
        ).head(3)
        # Preserve every industry for the first and last occupation in a
        # chunk. Those are the only occupation groups that can be split by a
        # chunk boundary, so this keeps the final top-three ranking exact.
        source_groups = chunk[["fips_concat", "occsoc", "occ2010"]].copy()
        source_groups["fips_concat"] = normalize_county_fips(
            source_groups["fips_concat"]
        )
        boundary_mask = pd.Series(False, index=detailed.index)
        for boundary in [source_groups.iloc[0], source_groups.iloc[-1]]:
            boundary_mask |= (
                detailed["county_fips"].eq(str(boundary["fips_concat"]).strip())
                & detailed["occupation_code"].eq(str(boundary["occsoc"]).strip())
                & detailed["occupation"].eq(str(boundary["occ2010"]).strip())
            )
        industry_candidates.append(
            pd.concat([candidates, detailed[boundary_mask]], ignore_index=True)
            .drop_duplicates(OCCUPATION_GROUP_COLUMNS + ["industry"])
        )

    occupation_totals = (
        pd.concat(totals, ignore_index=True)
        .groupby(OCCUPATION_GROUP_COLUMNS, as_index=False, observed=True)[VALUE_COLUMNS]
        .sum()
    )
    candidates = (
        pd.concat(industry_candidates, ignore_index=True)
        .groupby(
            OCCUPATION_GROUP_COLUMNS + ["industry"], as_index=False, observed=True
        )[VALUE_COLUMNS]
        .sum()
    )
    common = select_common_industries(candidates)
    summary = (
        occupation_totals.merge(common, on=OCCUPATION_GROUP_COLUMNS, how="left")
        .assign(common_industries=lambda frame: frame["common_industries"].fillna(""))
        .sort_values(OCCUPATION_GROUP_COLUMNS, kind="stable")
        .reset_index(drop=True)
    )
    validate_occupation_summary(summary)
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
    parser.add_argument(
        "--occupation-output",
        type=Path,
        default=root / "data" / "2022_occupation_county_summary.csv.gz",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = build_summary(arguments.source, arguments.output, arguments.chunksize)
    print(f"Wrote {len(result):,} county-industry rows to {arguments.output}")
    occupation_result = build_occupation_summary(
        arguments.source, arguments.occupation_output, arguments.chunksize
    )
    print(
        f"Wrote {len(occupation_result):,} county-occupation rows to "
        f"{arguments.occupation_output}"
    )
