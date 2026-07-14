"""Data preparation for the main county dashboard."""

import numpy as np
import pandas as pd
import streamlit as st

from . import data


DEFAULT_STATE = "CA"
DEFAULT_COUNTY = "Los Angeles County, CA"


@st.cache_resource
def load_dashboard_data():
    """Load and prepare the dashboard's shared, read-only DataFrames once.

    ``cache_resource`` intentionally returns the same DataFrame objects on each
    Streamlit rerun. Callers must therefore treat these frames as immutable and
    make a copy before changing their contents.
    """
    national_df, long_df, cbp_df, tradserv_df = data.load_data()
    grad_df = data.load_grad_data()
    national_df, long_df, wide_df = prepare_national_data(
        national_df,
        long_df,
        cbp_df,
        tradserv_df,
        grad_df,
    )
    return national_df, long_df, cbp_df, tradserv_df, grad_df, wide_df


def prepare_national_data(national_df, long_df, cbp_df, tradserv_df, grad_df):
    """Build the enriched county frames used throughout the main dashboard."""
    graduate_columns = grad_df[
        ["county_fips", "total_fouryear_grads_2022", "total_subba_grads_2022"]
    ].copy()
    graduate_columns["county_fips"] = graduate_columns["county_fips"].astype(float)
    national_df = national_df.merge(
        graduate_columns,
        left_on="countyid",
        right_on="county_fips",
        how="left",
    ).drop(columns="county_fips")
    national_df["total_fouryear_grads_2022"] = national_df[
        "total_fouryear_grads_2022"
    ].fillna(0)
    national_df["total_subba_grads_2022"] = national_df[
        "total_subba_grads_2022"
    ].fillna(0)

    working_population_column = next(
        (
            column
            for column in [
                "total_workers2022",
                "total_workers",
                "employed_workers_2022",
            ]
            if column in national_df.columns
        ),
        None,
    )
    if working_population_column:
        denominator = national_df[working_population_column].replace(0, float("nan"))
        national_df["fouryear_grads_per_wap_2022"] = (
            national_df["total_fouryear_grads_2022"] / denominator
        )
        national_df["subba_grads_per_wap_2022"] = (
            national_df["total_subba_grads_2022"] / denominator
        )
    else:
        national_df["fouryear_grads_per_wap_2022"] = float("nan")
        national_df["subba_grads_per_wap_2022"] = float("nan")

    planning_regions = national_df["county_name"].str.contains(
        "Planning Region", case=False, na=False
    )
    national_df = national_df[~planning_regions].copy()
    long_planning_regions = long_df["county_name"].str.contains(
        "Planning Region", case=False, na=False
    )
    long_df = long_df[~long_planning_regions].copy()

    wide_df = national_df.copy()
    if "workagepop" in wide_df.columns:
        wide_df["qpop5"] = pd.qcut(
            wide_df["workagepop"],
            q=5,
            labels=[
                "Quintile 1 (Smallest)",
                "Quintile 2",
                "Quintile 3",
                "Quintile 4",
                "Quintile 5 (Largest)",
            ],
            duplicates="drop",
        )
    else:
        wide_df["qpop5"] = wide_df["qpop"]

    total_employment = cbp_df.groupby("countyid")["emp"].sum().rename(
        "_total_emp_2016"
    )
    tradable_employment = tradserv_df.groupby("countyid")["emp"].sum().rename(
        "_tradserv_emp_2016"
    )
    tradable_share = (
        tradable_employment / total_employment.replace(0, float("nan")) * 100
    ).rename("tradserv_pct_2016")
    wide_df = wide_df.merge(
        tradable_share, left_on="countyid", right_index=True, how="left"
    )
    wide_df = wide_df.merge(
        total_employment, left_on="countyid", right_index=True, how="left"
    )
    wide_df["_total_emp_2016"] = wide_df["_total_emp_2016"].replace(
        0, float("nan")
    )
    if "tradserv_exp_emp_2017_2022" in wide_df.columns:
        wide_df["tradserv_exp_pct_2016emp"] = (
            wide_df["tradserv_exp_emp_2017_2022"].astype(float)
            / wide_df["_total_emp_2016"].astype(float)
            * 100
        )
    else:
        wide_df["tradserv_exp_pct_2016emp"] = float("nan")

    if "pct_star_midupp" in long_df.columns:
        middle_upper_2022 = (
            long_df[long_df["year"] == 2022]
            .drop_duplicates(subset=["countyid"])[["countyid", "pct_star_midupp"]]
            .rename(columns={"pct_star_midupp": "pct_star_midupp_2022"})
        )
        wide_df = wide_df.merge(middle_upper_2022, on="countyid", how="left")

    return national_df, long_df, wide_df


def get_state_options(national_df, default_state=DEFAULT_STATE):
    states = np.sort(national_df["state"].unique())
    matches = np.where(states == default_state)[0]
    default_index = int(matches[0]) if len(matches) else 0
    return states, default_index


def get_county_options(national_df, state, default_county=DEFAULT_COUNTY):
    state_df = national_df[national_df["state"] == state]
    counties = np.sort(state_df["county_name"].unique())
    matches = np.where(counties == default_county)[0]
    default_index = int(matches[0]) if len(matches) else 0
    return state_df, counties, default_index


def prepare_county_data(
    state_df,
    long_df,
    cbp_df,
    tradserv_df,
    grad_df,
    county,
):
    """Select county frames and calculate county-level display values."""
    county_df = state_df[state_df["county_name"] == county]
    county_long_df = long_df[long_df["county_name"] == county]
    county_id = county_df["countyid"].iloc[0]

    county_cbp_df = cbp_df[
        (cbp_df["countyid"] == county_id) & (cbp_df["emp"] > 1.0)
    ].copy()
    tradable_row = tradserv_df[tradserv_df["countyid"] == county_id]
    tradserv_emp = tradable_row["emp"].iloc[0] if len(tradable_row) > 0 else 0
    cbp_all = cbp_df[cbp_df["countyid"] == county_id]
    total_emp_2016 = cbp_all["emp"].sum()
    tradserv_pct = (
        round(100 * tradserv_emp / total_emp_2016, 1) if total_emp_2016 > 0 else 0
    )

    manufacturing = cbp_all[
        (cbp_all["sic87dd"] >= 2000) & (cbp_all["sic87dd"] <= 3999)
    ]
    mfg_emp_2016 = round(manufacturing["emp"].sum(), 0)
    mfg_pct_2016 = (
        round(100 * mfg_emp_2016 / total_emp_2016, 1)
        if total_emp_2016 > 0
        else 0
    )

    total_jobs_2022 = (
        round(county_df["employed_workers_2022"].iloc[0], 0)
        if len(county_df) > 0
        else 0
    )
    college_jobs_2022 = (
        round(county_df["employed_college2022"].iloc[0], 0)
        if len(county_df) > 0
        else 0
    )
    noncollege_jobs_2022 = (
        round(county_df["employed_STARs_2022"].iloc[0], 0)
        if len(county_df) > 0
        else 0
    )

    graduate_row = grad_df[grad_df["county_fips"] == int(county_id)]
    if len(graduate_row) > 0:
        pub_fouryear_grads_2022 = round(
            graduate_row["pub_fouryear_grads_2022"].iloc[0], 0
        )
        pub_subba_grads_2022 = round(
            graduate_row["pub_subba_grads_2022"].iloc[0], 0
        )
        priv_fouryear_grads_2022 = round(
            graduate_row["priv_fouryear_grads_2022"].iloc[0], 0
        )
        priv_subba_grads_2022 = round(
            graduate_row["priv_subba_grads_2022"].iloc[0], 0
        )
    else:
        pub_fouryear_grads_2022 = 0
        pub_subba_grads_2022 = 0
        priv_fouryear_grads_2022 = 0
        priv_subba_grads_2022 = 0

    return {
        "county_df": county_df,
        "county_long_df": county_long_df,
        "county_id": county_id,
        "county_cbp_df": county_cbp_df,
        "tradserv_emp": tradserv_emp,
        "tradserv_pct": tradserv_pct,
        "mfg_emp_2016": mfg_emp_2016,
        "mfg_pct_2016": mfg_pct_2016,
        "total_jobs_2022": total_jobs_2022,
        "college_jobs_2022": college_jobs_2022,
        "noncollege_jobs_2022": noncollege_jobs_2022,
        "pub_fouryear_grads_2022": pub_fouryear_grads_2022,
        "pub_subba_grads_2022": pub_subba_grads_2022,
        "priv_fouryear_grads_2022": priv_fouryear_grads_2022,
        "priv_subba_grads_2022": priv_subba_grads_2022,
    }


def calculate_county_stats(county_df):
    """Calculate the existing overview metrics for one county."""
    star_wage = round(county_df["star_median2022"].iloc[0], 0)
    college_wage = round(county_df["college_median2022"].iloc[0], 0)
    star_emp = round(county_df["star_emp_rate_2022"].iloc[0], 2)
    college_emp = round(county_df["emp_rate_college2022"].iloc[0], 2)
    pct_educ2022 = round(100 * county_df["educ_pct_total_stloc2022"].iloc[0], 2)
    ppupil_educ2022 = round(county_df["ppupil_deflate_2022"].iloc[0], 2)
    job_loss = round(county_df["pred_emp_loss"].iloc[0], 0)
    job_gain = round(county_df["pred_emp_gain"].iloc[0], 0)
    pct_job_loss = round(county_df["pct_pred_emp_loss"].iloc[0], 1)
    pct_job_gain = round(county_df["pct_pred_emp_gain"].iloc[0], 1)
    mfgemp_loss = max(
        0,
        round(
            county_df["mfgemp2000"].iloc[0] - county_df["mfgemp2011"].iloc[0],
            0,
        ),
    )
    serv_exp_job = round(county_df["tradserv_exp_emp_2017_2022"].iloc[0], 0)
    pct_serv_exp_job = (
        round(county_df["tradserv_exp_pct_2016emp"].iloc[0], 2)
        if "tradserv_exp_pct_2016emp" in county_df.columns
        else None
    )
    return {
        "star_wage": star_wage,
        "college_wage": college_wage,
        "star_emp": star_emp,
        "college_emp": college_emp,
        "pct_educ2022": pct_educ2022,
        "ppupil_educ2022": ppupil_educ2022,
        "job_loss": job_loss,
        "job_gain": job_gain,
        "pct_job_loss": pct_job_loss,
        "pct_job_gain": pct_job_gain,
        "mfgemp_loss": mfgemp_loss,
        "serv_exp_job": serv_exp_job,
        "pct_serv_exp_job": pct_serv_exp_job,
    }


def rank_within_population_quintile(
    wide_df,
    county_id,
    population_quintile,
    column,
    higher_is_better=True,
):
    if column not in wide_df.columns or population_quintile is None:
        return None, None
    bucket = wide_df[wide_df["qpop5"] == population_quintile][
        ["countyid", column]
    ].dropna(subset=[column])
    count = len(bucket)
    if count == 0:
        return None, None
    county_value = bucket[bucket["countyid"] == county_id][column]
    if len(county_value) == 0:
        return None, None
    value = county_value.iloc[0]
    rank = int(
        (
            bucket[column] > value
            if higher_is_better
            else bucket[column] < value
        ).sum()
    ) + 1
    return rank, count
