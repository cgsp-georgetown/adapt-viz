"""Streamlit entry point for the American Dream dashboard."""

import streamlit as st

from dashboard_lib.main_data import (
    calculate_county_stats,
    load_dashboard_data,
    prepare_county_data,
)
from dashboard_lib.main_views import (
    apply_dashboard_style,
    render_county_selector,
    render_dashboard,
)


st.set_page_config(page_title="Hello", page_icon="🚚", layout="wide")


def main():
    apply_dashboard_style()
    (
        national_df,
        long_df,
        cbp_df,
        tradserv_df,
        grad_df,
        wide_df,
        industry_county_df,
        occupation_county_df,
    ) = load_dashboard_data()
    state_df, county = render_county_selector(national_df)
    county_data = prepare_county_data(
        state_df,
        long_df,
        cbp_df,
        tradserv_df,
        grad_df,
        industry_county_df,
        occupation_county_df,
        county,
    )
    stats = calculate_county_stats(county_data["county_df"])
    render_dashboard(wide_df, long_df, county, county_data, stats)


main()
