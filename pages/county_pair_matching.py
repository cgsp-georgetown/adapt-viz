import streamlit as st

from dashboard_lib.pair_matching import build_pairs, load_pool, load_timeseries
from dashboard_lib.pair_views import (
    render_page_header,
    render_pair_comparison,
    render_pair_filters,
    render_pair_results,
)


st.set_page_config(page_title="County Pair Matching", layout="wide")


def main():
    render_page_header()
    pool = load_pool()
    filters = render_pair_filters(pool)
    pairs = build_pairs(pool, **filters)
    render_pair_results(pairs)

    if not pairs.empty and "county_name_H" in pairs.columns:
        render_pair_comparison(pairs, load_timeseries())


main()
