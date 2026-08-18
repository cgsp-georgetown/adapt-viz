import streamlit as st

from dashboard_lib.pair_matching import (
    load_ppupil_spending,
    load_shock_percentiles,
    load_similarity_matches,
    load_timeseries,
)
from dashboard_lib.pair_views import render_similarity_matches


st.set_page_config(page_title="County Pair Matching", layout="wide")


def main():
    render_similarity_matches(
        load_similarity_matches(),
        load_timeseries(),
        load_shock_percentiles(),
        load_ppupil_spending(),
    )


main()
