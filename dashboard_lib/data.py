import pandas as pd
import streamlit as st
from .paths import (
    COUNTY_WIDE,
    COUNTY_LONG_DTA,
    COUNTY_LONG_CSV,
    COUNTY_INDEX,
    COUNTY_POST_INDEX,
    CBP_COUNTY_2016,
    TRADSERV_2016,
    COLLEGE_PANEL,
    CZONE_COUNTY,
    SIMILARITY_MATRIX,
    INDUSTRY_COUNTY_2022,
    OCCUPATION_COUNTY_2022,
)

@st.cache_data  # This function will be cached to optimize loading
def load_data():
    return pd.read_stata(COUNTY_WIDE), pd.read_stata(COUNTY_LONG_DTA), pd.read_csv(CBP_COUNTY_2016), pd.read_csv(TRADSERV_2016)

@st.cache_data
def load_grad_data():
    df = pd.read_stata(COLLEGE_PANEL)

    # Filter early to reduce the amount of data processed.
    df2022 = df.loc[
        df["year"].eq(2022),
        ["county_fips", "college_label", "level", "numbergraduates"],
    ].copy()

    df2022["county_fips"] = df2022["county_fips"].astype("Int64")

    # Calculate each condition once.
    is_public = df2022["college_label"].str.contains("public", na=False)
    is_private = df2022["college_label"].str.contains("private", na=False)
    is_fouryear = df2022["level"].eq("4+ years")
    is_subba = df2022["level"].ne("4+ years")

    graduates = df2022["numbergraduates"]

    # Create the six output variables using vectorized masks.
    df2022["pub_fouryear_grads_2022"] = graduates.where(
        is_public & is_fouryear, 0
    )
    df2022["pub_subba_grads_2022"] = graduates.where(
        is_public & is_subba, 0
    )
    df2022["priv_fouryear_grads_2022"] = graduates.where(
        is_private & is_fouryear, 0
    )
    df2022["priv_subba_grads_2022"] = graduates.where(
        is_private & is_subba, 0
    )
    df2022["total_fouryear_grads_2022"] = graduates.where(
        is_fouryear, 0
    )
    df2022["total_subba_grads_2022"] = graduates.where(
        is_subba, 0
    )

    output_columns = [
        "pub_fouryear_grads_2022",
        "pub_subba_grads_2022",
        "priv_fouryear_grads_2022",
        "priv_subba_grads_2022",
        "total_fouryear_grads_2022",
        "total_subba_grads_2022",
    ]

    grads = (
        df2022.groupby("county_fips", as_index=False)[output_columns]
        .sum()
    )

    return grads


@st.cache_data
def load_industry_county_data():
    """Load the pre-aggregated 2022 county-by-industry worker estimates."""
    return pd.read_csv(
        INDUSTRY_COUNTY_2022,
        dtype={"county_fips": "string"},
    )


@st.cache_data
def load_occupation_county_data():
    """Load the pre-aggregated 2022 county-by-occupation worker estimates."""
    return pd.read_csv(
        OCCUPATION_COUNTY_2022,
        dtype={
            "county_fips": "string",
            "occupation_code": "string",
        },
        keep_default_na=False,
    )

