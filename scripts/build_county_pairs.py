"""Match each county with the most similar county (or two) for comparison analysis.

Counties are grouped by RUCC_2013 (rural-urban continuum code), then
subdivided by Economic_Type_Label and Low_Education_2015_Update. Counties are
matched only within that exact group -- there is no relaxation across groups.
Within a group, candidates are sorted by total_workers2022 (labor force size,
from county_all_vars_wide.dta) and matched with their nearest neighbor in
that ordering. Groups with an odd number of members form one trio (the three
closest counties by labor force size share the match) instead of leaving a
county unmatched, so only counties whose exact group has no other member at
all (a group of size 1) are left without a match.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

GROUP_COLS = ["RUCC_2013", "Economic_Type_Label", "Low_Education_2015_Update"]
MATCH_TIER = "rucc_econtype_lowed"
LOWED_DROPPED_TIER = "rucc_econtype_lowed_dropped"
ECONTYPE_ONLY_TIER = "econtype_only_nearest_rucc_pop"


def load_merged(
    rucc_path: Path, typology_path: Path, labor_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and merge the RUCC, typology, and labor-force sources on county FIPS code."""
    rucc = pd.read_stata(rucc_path)[["countyid", "RUCC_2013"]]

    typ = pd.read_csv(typology_path)
    typ = typ.rename(columns={"FIPStxt": "countyid"})
    typ = typ[
        [
            "countyid",
            "State",
            "County_name",
            "Economic_Type_Label",
            "Low_Education_2015_Update",
        ]
    ]

    labor = pd.read_stata(labor_path, columns=["countyid", "total_workers2022"])
    labor["countyid"] = labor["countyid"].astype("int64")

    merged = rucc.merge(typ, on="countyid", how="inner")
    rucc_only = rucc[~rucc["countyid"].isin(typ["countyid"])]
    typ_only = typ[~typ["countyid"].isin(rucc["countyid"])]

    merged = merged.merge(labor, on="countyid", how="left")
    return merged.reset_index(drop=True), rucc_only, typ_only


def pair_counties(df: pd.DataFrame) -> tuple[list[dict], list[int], dict[int, int]]:
    """Match counties within their exact RUCC/Economic-Type/Low-Education group.

    No relaxation across groups. Within a group, candidates are sorted by
    total_workers2022 (labor force size, missing values last, ties broken by
    countyid) and matched with their nearest neighbor in that ordering --
    minimizing the labor-force size gap within each match. A group with an
    even number of members forms pairs; an odd-sized group with more than
    one member forms pairs down to its last three counties, which share a
    single trio match instead of leaving one county out. A group of exactly
    one county has no possible match and is reported as unmatched.

    Also returns each county's group (candidate pool) size, so callers can
    tell a county with a single possible partner (pool size 2) from one that
    had multiple candidates to choose from (pool size > 2).
    """
    match_groups: list[dict] = []
    unmatched: list[int] = []
    group_size: dict[int, int] = {}

    for key, group in df.groupby(GROUP_COLS, sort=False):
        ordered = group.sort_values(
            ["total_workers2022", "countyid"],
            na_position="last",
        )
        ids = ordered["countyid"].tolist()
        n = len(ids)
        for cid in ids:
            group_size[cid] = n

        if n == 1:
            unmatched.append(ids[0])
            continue

        if n % 2 == 0:
            for i in range(0, n, 2):
                match_groups.append({"members": ids[i : i + 2], "key": key})
        else:
            i = 0
            while i < n - 3:
                match_groups.append({"members": ids[i : i + 2], "key": key})
                i += 2
            match_groups.append({"members": ids[i : i + 3], "key": key})

    return match_groups, unmatched, group_size


def find_relaxed_matches(df: pd.DataFrame, unmatched: list[int]) -> tuple[list[dict], list[int]]:
    """Give each remaining singleton county its own closest match, low-education dropped.

    A singleton has no other county sharing its exact RUCC/Economic-Type/
    Low-Education group. Here Low_Education_2015_Update is dropped from the
    grouping key, and the singleton is matched to whichever county in the
    wider RUCC/Economic-Type pool has the closest total_workers2022 --
    including counties that already have their own primary match.

    This is a one-way "closest county" assignment, not a mutual pairing: the
    target keeps whatever primary match it already had. Multiple singletons
    can therefore point to the same closest county (a "love triangle") --
    unlike the trio case in pair_counties, this never creates a shared
    three-way match. Singletons whose RUCC/Economic-Type pool is also empty
    stay unmatched.
    """
    lookup = df.set_index("countyid")
    relaxed_matches: list[dict] = []
    still_unmatched: list[int] = []

    for cid in unmatched:
        row = df[df["countyid"] == cid].iloc[0]
        pool = df[
            (df["RUCC_2013"] == row["RUCC_2013"])
            & (df["Economic_Type_Label"] == row["Economic_Type_Label"])
            & (df["countyid"] != cid)
        ]
        if pool.empty:
            still_unmatched.append(cid)
            continue

        own_workers = row["total_workers2022"]
        candidates = pool.copy()
        if pd.notna(own_workers):
            candidates["_gap"] = (candidates["total_workers2022"] - own_workers).abs()
        else:
            candidates["_gap"] = candidates["total_workers2022"].isna().map({True: 0, False: 1})
        candidates = candidates.sort_values(["_gap", "countyid"], na_position="last")
        closest = candidates.iloc[0]

        relaxed_matches.append(
            {
                "countyid": cid,
                "closest_countyid": int(closest["countyid"]),
                "gap": (
                    abs(closest["total_workers2022"] - own_workers)
                    if pd.notna(own_workers) and pd.notna(closest["total_workers2022"])
                    else None
                ),
                "tier": LOWED_DROPPED_TIER,
            }
        )

    return relaxed_matches, still_unmatched


def find_econtype_only_matches(df: pd.DataFrame, unmatched: list[int]) -> tuple[list[dict], list[int]]:
    """Give each still-unmatched county a closest match by Economic_Type_Label alone.

    Both RUCC_2013 and Low_Education_2015_Update are dropped here -- only
    Economic_Type_Label must match. Among same-type counties, candidates are
    ranked first by closest RUCC_2013 (rural-urban continuum distance), then
    by closest total_workers2022 (labor force / population size) as a
    tiebreaker. Same one-way "closest county" semantics as
    find_relaxed_matches: the target keeps its own primary match.
    """
    relaxed_matches: list[dict] = []
    still_unmatched: list[int] = []

    for cid in unmatched:
        row = df[df["countyid"] == cid].iloc[0]
        pool = df[
            (df["Economic_Type_Label"] == row["Economic_Type_Label"]) & (df["countyid"] != cid)
        ].copy()
        if pool.empty:
            still_unmatched.append(cid)
            continue

        pool["_rucc_gap"] = (pool["RUCC_2013"] - row["RUCC_2013"]).abs()
        own_workers = row["total_workers2022"]
        if pd.notna(own_workers):
            pool["_pop_gap"] = (pool["total_workers2022"] - own_workers).abs()
        else:
            pool["_pop_gap"] = pool["total_workers2022"].isna().map({True: 0, False: 1})
        pool = pool.sort_values(["_rucc_gap", "_pop_gap", "countyid"], na_position="last")
        closest = pool.iloc[0]

        relaxed_matches.append(
            {
                "countyid": cid,
                "closest_countyid": int(closest["countyid"]),
                "gap": (
                    abs(closest["total_workers2022"] - own_workers)
                    if pd.notna(own_workers) and pd.notna(closest["total_workers2022"])
                    else None
                ),
                "tier": ECONTYPE_ONLY_TIER,
            }
        )

    return relaxed_matches, still_unmatched


def attach_relaxed_details(relaxed_matches: list[dict], df: pd.DataFrame, start_id: int) -> pd.DataFrame:
    """Build output rows for one-way relaxed matches."""
    lookup = df.set_index("countyid")
    rows = []
    for offset, match in enumerate(relaxed_matches):
        cid, target = match["countyid"], match["closest_countyid"]
        row = {
            "match_id": start_id + offset,
            "match_size": 2,
            "mutual_match": False,
            "countyid_1": cid,
            "County_name_1": lookup.loc[cid, "County_name"],
            "State_1": lookup.loc[cid, "State"],
            "total_workers2022_1": lookup.loc[cid, "total_workers2022"],
            "countyid_2": target,
            "County_name_2": lookup.loc[target, "County_name"],
            "State_2": lookup.loc[target, "State"],
            "total_workers2022_2": lookup.loc[target, "total_workers2022"],
            "countyid_3": pd.NA,
            "County_name_3": pd.NA,
            "State_3": pd.NA,
            "total_workers2022_3": pd.NA,
            "RUCC_2013": lookup.loc[cid, "RUCC_2013"],
            "Economic_Type_Label": lookup.loc[cid, "Economic_Type_Label"],
            "Low_Education_2015_Update": pd.NA,
            "max_labor_force_gap": match["gap"],
            "match_tier": match["tier"],
        }
        rows.append(row)
    ordered = [
        "match_id", "match_size", "mutual_match",
        "countyid_1", "County_name_1", "State_1", "total_workers2022_1",
        "countyid_2", "County_name_2", "State_2", "total_workers2022_2",
        "countyid_3", "County_name_3", "State_3", "total_workers2022_3",
        "RUCC_2013", "Economic_Type_Label", "Low_Education_2015_Update",
        "max_labor_force_gap", "match_tier",
    ]
    return pd.DataFrame(rows, columns=ordered)


def attach_details(match_groups: list[dict], df: pd.DataFrame) -> pd.DataFrame:
    """Build the output table: one row per match, up to three member counties."""
    detail_cols = {
        "countyid": {},
        "County_name": {},
        "State": {},
        "total_workers2022": {},
    }
    lookup = df.set_index("countyid")

    rows = []
    for match_id, match in enumerate(match_groups, start=1):
        members = match["members"]
        rucc, econ_type, low_ed = match["key"]
        workers = [lookup.loc[cid, "total_workers2022"] for cid in members]
        finite_workers = [w for w in workers if pd.notna(w)]
        max_gap = max(finite_workers) - min(finite_workers) if len(finite_workers) > 1 else None

        row = {
            "match_id": match_id,
            "match_size": len(members),
            "mutual_match": True,
            "RUCC_2013": rucc,
            "Economic_Type_Label": econ_type,
            "Low_Education_2015_Update": low_ed,
            "max_labor_force_gap": max_gap,
            "match_tier": MATCH_TIER,
        }
        for slot in range(1, 4):
            if slot <= len(members):
                cid = members[slot - 1]
                row[f"countyid_{slot}"] = cid
                row[f"County_name_{slot}"] = lookup.loc[cid, "County_name"]
                row[f"State_{slot}"] = lookup.loc[cid, "State"]
                row[f"total_workers2022_{slot}"] = lookup.loc[cid, "total_workers2022"]
            else:
                row[f"countyid_{slot}"] = pd.NA
                row[f"County_name_{slot}"] = pd.NA
                row[f"State_{slot}"] = pd.NA
                row[f"total_workers2022_{slot}"] = pd.NA
        rows.append(row)

    ordered = (
        ["match_id", "match_size", "mutual_match"]
        + [f"{field}_{slot}" for slot in range(1, 4) for field in ("countyid", "County_name", "State", "total_workers2022")]
        + [
            "RUCC_2013",
            "Economic_Type_Label",
            "Low_Education_2015_Update",
            "max_labor_force_gap",
            "match_tier",
        ]
    )
    return pd.DataFrame(rows, columns=ordered)


def print_status_report(
    df: pd.DataFrame,
    matches_df: pd.DataFrame,
    unmatched_before_relaxation: list[int],
    still_unmatched: list[int],
    group_size: dict[int, int],
    rucc_only: pd.DataFrame,
    typ_only: pd.DataFrame,
) -> None:
    total = len(df)
    mutual = matches_df[matches_df["mutual_match"]]
    relaxed = matches_df[~matches_df["mutual_match"]]

    matched_counties = int(mutual["match_size"].sum())
    n_pairs = int((mutual["match_size"] == 2).sum())
    n_trios = int((mutual["match_size"] == 3).sum())
    n_relaxed = len(relaxed)
    unique_partner = sum(1 for cid in group_size if group_size[cid] == 2)
    multi_candidate = matched_counties - unique_partner

    print("=" * 60)
    print("COUNTY MATCHING STATUS REPORT (no cross-group relaxation, low-ed relaxed for leftovers)")
    print("=" * 60)
    print(f"Counties in RUCC source only (dropped, no typology match): {len(rucc_only)}")
    print(f"Counties in typology source only (dropped, no RUCC match): {len(typ_only)}")
    print(f"Counties available for matching: {total}")
    print(f"Counties with a mutual match (exact group):     {matched_counties} ({matched_counties / total:.1%})")
    print(f"Counties given a one-way closest match (low-ed dropped): {n_relaxed} ({n_relaxed / total:.1%})")
    print(f"Counties still without any match:               {len(still_unmatched)} ({len(still_unmatched) / total:.1%})")
    print(f"Total mutual matches formed:            {len(mutual)}  ({n_pairs} pairs + {n_trios} trios)")
    print()
    print("Of the counties with a mutual match:")
    print(f"  Unique partner (group size = 2, only one possible pairing): {unique_partner}")
    print(f"  Multiple candidates (group size > 2, chosen by closest labor force size): {multi_candidate}")
    print(f"  Counties placed in a trio (odd-sized group of 3+): {n_trios * 3}")
    print()

    for tier_name, label in [
        (LOWED_DROPPED_TIER, "One-way relaxed matches (Low_Education_2015_Update dropped):"),
        (ECONTYPE_ONLY_TIER, "One-way relaxed matches (RUCC_2013 + Low_Education dropped, nearest RUCC then population):"),
    ]:
        tier_rows = relaxed[relaxed["match_tier"] == tier_name]
        if tier_rows.empty:
            continue
        print(label)
        for _, r in tier_rows.iterrows():
            gap = f"{r['max_labor_force_gap']:,.0f}" if pd.notna(r["max_labor_force_gap"]) else "n/a"
            print(
                f"  {r['County_name_1']}, {r['State_1']} (FIPS {int(r['countyid_1'])}) -> closest: "
                f"{r['County_name_2']}, {r['State_2']} (FIPS {int(r['countyid_2'])}), gap {gap} workers"
            )
        print()

    if still_unmatched:
        print("Still unmatched (no other county even shares RUCC + Economic Type):")
        for cid in still_unmatched:
            row = df[df["countyid"] == cid].iloc[0]
            print(f"  {row['County_name']}, {row['State']} (FIPS {cid}) -- RUCC {row['RUCC_2013']}, {row['Economic_Type_Label']}")
        print()

    gaps = mutual["max_labor_force_gap"].dropna()
    if not gaps.empty:
        print("Labor force size gap within mutual matches (total_workers2022, max pairwise |diff|):")
        print(f"  Median gap: {gaps.median():,.0f} workers")
        print(f"  Mean gap:   {gaps.mean():,.0f} workers")
        print(f"  Max gap:    {gaps.max():,.0f} workers")
        print()

    print("Matches per RUCC_2013 group (mutual matches only):")
    per_rucc = mutual.groupby("RUCC_2013")["match_id"].count().sort_index()
    for rucc_value, count in per_rucc.items():
        print(f"  RUCC_2013 = {rucc_value:<3} {count:>5} matches")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rucc-source", type=Path, default=root / "data" / "county_rural_urban_2013.dta"
    )
    parser.add_argument(
        "--typology-source",
        type=Path,
        default=root / "data" / "erscountytypology2015edition.csv",
    )
    parser.add_argument(
        "--labor-source",
        type=Path,
        default=root / "data" / "county_all_vars_wide.dta",
    )
    parser.add_argument(
        "--output", type=Path, default=root / "data" / "county_pairs_2015.csv"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df, rucc_only, typ_only = load_merged(args.rucc_source, args.typology_source, args.labor_source)

    match_groups, unmatched, group_size = pair_counties(df)
    matches_df = attach_details(match_groups, df)

    lowed_dropped_matches, still_unmatched = find_relaxed_matches(df, unmatched)
    econtype_only_matches, still_unmatched = find_econtype_only_matches(df, still_unmatched)
    all_relaxed = lowed_dropped_matches + econtype_only_matches
    if all_relaxed:
        relaxed_df = attach_relaxed_details(all_relaxed, df, start_id=len(matches_df) + 1)
        matches_df = pd.concat([matches_df, relaxed_df], ignore_index=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    matches_df.to_csv(args.output, index=False)
    print(f"Wrote {len(matches_df):,} matches to {args.output}\n")

    print_status_report(df, matches_df, unmatched, still_unmatched, group_size, rucc_only, typ_only)


if __name__ == "__main__":
    main()
