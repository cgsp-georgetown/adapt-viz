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
)

@st.cache_data  # This function will be cached to optimize loading
def load_data():
    return pd.read_stata(COUNTY_WIDE), pd.read_stata(COUNTY_LONG_DTA), pd.read_csv(CBP_COUNTY_2016), pd.read_csv(TRADSERV_2016)

@st.cache_data
def load_grad_data():
    df = pd.read_stata(COLLEGE_PANEL)
    df2022 = df[df["year"] == 2022].copy()
    df2022["county_fips"] = df2022["county_fips"].astype("Int64")
    grads = df2022.groupby("county_fips").apply(
        lambda g: pd.Series({
            "pub_fouryear_grads_2022":  g.loc[g["college_label"].str.contains("public",  na=False) & (g["level"] == "4+ years"), "numbergraduates"].sum(),
            "pub_subba_grads_2022":     g.loc[g["college_label"].str.contains("public",  na=False) & (g["level"] != "4+ years"), "numbergraduates"].sum(),
            "priv_fouryear_grads_2022": g.loc[g["college_label"].str.contains("private", na=False) & (g["level"] == "4+ years"), "numbergraduates"].sum(),
            "priv_subba_grads_2022":    g.loc[g["college_label"].str.contains("private", na=False) & (g["level"] != "4+ years"), "numbergraduates"].sum(),
            "total_fouryear_grads_2022": g.loc[g["level"] == "4+ years", "numbergraduates"].sum(),
            "total_subba_grads_2022":    g.loc[g["level"] != "4+ years", "numbergraduates"].sum(),
        })
    ).reset_index()
    return grads

