"""Data preparation and matching logic for the county-pair dashboard."""

import pandas as pd
import streamlit as st

from .paths import COUNTY_LONG_CSV, COUNTY_WIDE, SIMILARITY_MATRIX


CONT_SIM_VARS = [
    "mfg_empsh",
    "ag_empsh",
    "gov_empsh",
    "college_lf_share_1990",
]


def classify_recovery(row):
    """Classify recovery from employment and income growth indicators."""
    emp = row.get("d_pct_star_emp_2000_2022", 0) > 0
    inc = row.get("d_star_med_pct_2000_2022", 0) > 0
    if emp and inc:
        return "both"
    if emp:
        return "emp"
    if inc:
        return "inc"
    return "loss"


@st.cache_data
def load_timeseries():
    long = pd.read_csv(COUNTY_LONG_CSV)
    long = long[long["year"].between(1990, 2022)].copy()
    long["year"] = long["year"].astype(int)
    keep = ["countyid", "county_name", "year", "star_median", "star_pop"]
    keep = [column for column in keep if column in long.columns]
    return long[keep].dropna(subset=["year"])


@st.cache_data
def load_pool():
    wide = pd.read_stata(COUNTY_WIDE)

    ppupil_col = next(
        (
            column
            for column in [
                "ppupil_deflate_1990",
                "ppupil_deflate1990",
                "ppupil1990",
                "spend_ppupil_1990",
                "ppupil_deflate_2022",
            ]
            if column in wide.columns
        ),
        None,
    )
    shock_col = next(
        (
            column
            for column in ["d_m_usdev82000_2011", "d_m_usdev8_2000_2011"]
            if column in wide.columns
        ),
        None,
    )

    wide_keep = ["countyid", "statefips", "state"]
    if ppupil_col:
        wide_keep.append(ppupil_col)
    if shock_col:
        wide_keep.append(shock_col)
    wide_keep = [column for column in wide_keep if column in wide.columns]
    wide = wide[wide_keep].copy()
    if ppupil_col and ppupil_col != "ppupil_deflate1990":
        wide = wide.rename(columns={ppupil_col: "ppupil_deflate1990"})
    if shock_col and shock_col != "d_m_usdev82000_2011":
        wide = wide.rename(columns={shock_col: "d_m_usdev82000_2011"})

    long = pd.read_csv(COUNTY_LONG_CSV)
    long = long[long["year"].isin([1990, 2000, 2011, 2022])].copy()
    long["year"] = long["year"].astype(int)

    ts_cols = [
        "countyid",
        "county_name",
        "year",
        "workagepop",
        "totalSTARS",
        "employed_STARs",
        "star_median",
        "mfgsh",
        "star_emp_rate",
    ]
    ts_cols = [column for column in ts_cols if column in long.columns]

    piv = long[ts_cols].pivot_table(
        index=["countyid", "county_name"],
        columns="year",
        values=[
            column
            for column in ts_cols
            if column not in ("countyid", "county_name")
        ],
        aggfunc="first",
    )
    piv.columns = [f"{value}_{year}" for value, year in piv.columns]
    piv = piv.reset_index()

    sim = pd.read_stata(SIMILARITY_MATRIX)
    sim_keep = ["countyid"] + [
        column
        for column in CONT_SIM_VARS + ["RUCC_2013", "Description"]
        if column in sim.columns
    ]
    sim = sim[sim_keep].copy()

    df = piv.merge(wide, on="countyid", how="inner")
    df = df.merge(sim, on="countyid", how="left")

    if "mfgsh_1990" in df.columns and "mfgsh_2011" in df.columns:
        df["d_mfg_job_pct_1990_2011"] = df["mfgsh_2011"] - df["mfgsh_1990"]

    if "star_median_2000" in df.columns and "star_median_2022" in df.columns:
        df["d_star_med_pct_2000_2022"] = (
            (df["star_median_2022"] - df["star_median_2000"])
            / df["star_median_2000"].replace(0, float("nan"))
        )

    if "employed_STARs_2000" in df.columns and "employed_STARs_2022" in df.columns:
        df["d_pct_star_emp_2000_2022"] = (
            (df["employed_STARs_2022"] - df["employed_STARs_2000"])
            / df["employed_STARs_2000"].replace(0, float("nan"))
        )

    df = df.dropna(
        subset=[
            column
            for column in [
                "ppupil_deflate1990",
                "d_star_med_pct_2000_2022",
                "d_pct_star_emp_2000_2022",
            ]
            if column in df.columns
        ]
    )

    df["recovery"] = df.apply(classify_recovery, axis=1)
    if "workagepop_1990" in df.columns:
        df["workagepop_1990"] = df["workagepop_1990"].round(0).astype("Int64")
    return df.reset_index(drop=True)


def build_pairs(
    pool,
    min_shock,
    min_ppupil_diff,
    recovery_filter,
    sim_pct,
    require_rucc,
    pop_range=None,
):
    sub = pool.copy()
    if min_shock is not None and "d_m_usdev82000_2011" in sub.columns:
        sub = sub[sub["d_m_usdev82000_2011"] >= min_shock]
    if pop_range is not None and "workagepop_1990" in sub.columns:
        sub = sub[sub["workagepop_1990"].between(pop_range[0], pop_range[1])]

    for variable in CONT_SIM_VARS:
        if variable in sub.columns:
            sub[f"{variable}_pct"] = sub[variable].rank(pct=True) * 100

    a = sub.add_suffix("_A").assign(_key=1)
    b = sub.add_suffix("_B").assign(_key=1)
    pairs = a.merge(b, on="_key").drop(columns="_key")

    pairs = pairs[pairs["statefips_A"] == pairs["statefips_B"]]
    pairs = pairs[pairs["countyid_A"] < pairs["countyid_B"]]

    if require_rucc and "RUCC_2013_A" in pairs.columns:
        pairs = pairs[pairs["RUCC_2013_A"] == pairs["RUCC_2013_B"]]

    for variable in CONT_SIM_VARS:
        col_a, col_b = f"{variable}_pct_A", f"{variable}_pct_B"
        if col_a in pairs.columns and col_b in pairs.columns:
            pairs = pairs[(pairs[col_a] - pairs[col_b]).abs() <= sim_pct]

    if "ppupil_deflate1990_A" not in pairs.columns:
        st.error("ppupil_deflate1990 not found — cannot compute spending difference.")
        return pd.DataFrame()

    pairs["ppupil_diff_raw"] = (
        pairs["ppupil_deflate1990_A"] - pairs["ppupil_deflate1990_B"]
    )
    pairs = pairs[pairs["ppupil_diff_raw"].abs() >= min_ppupil_diff]

    pairs["aligns_A"] = (
        (pairs["ppupil_diff_raw"] > 0)
        & (
            pairs["d_pct_star_emp_2000_2022_A"]
            > pairs["d_pct_star_emp_2000_2022_B"]
        )
        & (
            pairs["d_star_med_pct_2000_2022_A"]
            > pairs["d_star_med_pct_2000_2022_B"]
        )
    )
    pairs["aligns_B"] = (
        (pairs["ppupil_diff_raw"] < 0)
        & (
            pairs["d_pct_star_emp_2000_2022_B"]
            > pairs["d_pct_star_emp_2000_2022_A"]
        )
        & (
            pairs["d_star_med_pct_2000_2022_B"]
            > pairs["d_star_med_pct_2000_2022_A"]
        )
    )
    pairs = pairs[pairs["aligns_A"] | pairs["aligns_B"]].copy()

    hvars = [
        "countyid",
        "county_name",
        "state",
        "workagepop_1990",
        "ppupil_deflate1990",
        "d_star_med_pct_2000_2022",
        "d_pct_star_emp_2000_2022",
        "recovery",
        "totalSTARS_1990",
        "star_median_2000",
        "star_median_2022",
        "employed_STARs_2000",
        "employed_STARs_2022",
        "star_emp_rate_1990",
        "star_emp_rate_2011",
        "star_emp_rate_2022",
        "d_mfg_job_pct_1990_2011",
        "d_m_usdev82000_2011",
        "RUCC_2013",
        "Description",
    ] + CONT_SIM_VARS
    hvars = [variable for variable in hvars if variable + "_A" in pairs.columns]

    for variable in hvars:
        pairs[variable + "_H"] = pairs.apply(
            lambda row, value=variable: (
                row[value + "_A"] if row["aligns_A"] else row[value + "_B"]
            ),
            axis=1,
        )
        pairs[variable + "_L"] = pairs.apply(
            lambda row, value=variable: (
                row[value + "_B"] if row["aligns_A"] else row[value + "_A"]
            ),
            axis=1,
        )

    pairs["d_ppupil"] = (
        pairs["ppupil_deflate1990_H"] - pairs["ppupil_deflate1990_L"]
    )
    pairs["d_wage_growth"] = (
        pairs["d_star_med_pct_2000_2022_H"]
        - pairs["d_star_med_pct_2000_2022_L"]
    )
    pairs["d_emp_growth"] = (
        pairs["d_pct_star_emp_2000_2022_H"]
        - pairs["d_pct_star_emp_2000_2022_L"]
    )
    pairs["pair_score"] = (
        (pairs["d_ppupil"] / 100)
        + (pairs["d_wage_growth"] * 10)
        + (pairs["d_emp_growth"] * 10)
    )
    if (
        "d_m_usdev82000_2011_H" in pairs.columns
        and "d_m_usdev82000_2011_L" in pairs.columns
    ):
        pairs["pair_score"] -= (
            pairs["d_m_usdev82000_2011_H"]
            - pairs["d_m_usdev82000_2011_L"]
        ).abs()

    if "recovery_H" in pairs.columns:
        pairs = pairs[pairs["recovery_H"].isin(recovery_filter)]

    return pairs.sort_values("pair_score", ascending=False).reset_index(drop=True)
