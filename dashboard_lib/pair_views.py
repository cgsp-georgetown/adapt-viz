"""Streamlit views for the county-pair matching page."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .pair_matching import CONT_SIM_VARS


DISPLAY_COLUMNS = {
    "state_H": "State",
    "county_name_H": "High Spender",
    "county_name_L": "Low Spender",
    "Description_H": "RUCC Description",
    "d_ppupil": "Spending Diff ($)",
    "d_emp_growth": "Emp Growth Diff",
    "d_wage_growth": "Wage Growth Diff",
    "recovery_H": "Recovery (H)",
    "recovery_L": "Recovery (L)",
    "workagepop_1990_H": "Work-Age Pop 1990 (H)",
    "workagepop_1990_L": "Work-Age Pop 1990 (L)",
    "ppupil_deflate1990_H": "Per-Pupil 1990 (H)",
    "ppupil_deflate1990_L": "Per-Pupil 1990 (L)",
    "d_m_usdev82000_2011_H": "Shock (H)",
    "d_m_usdev82000_2011_L": "Shock (L)",
    "star_median_2000_H": "NC Wage 2000 (H)",
    "star_median_2022_H": "NC Wage 2022 (H)",
    "star_median_2000_L": "NC Wage 2000 (L)",
    "star_median_2022_L": "NC Wage 2022 (L)",
    "mfg_empsh_H": "Mfg Emp Share (H)",
    "mfg_empsh_L": "Mfg Emp Share (L)",
    "college_lf_share_1990_H": "College LF Share 1990 (H)",
    "college_lf_share_1990_L": "College LF Share 1990 (L)",
    "pair_score": "Pair Score",
}


def render_page_header():
    st.title("County Pair Matching")
    st.caption(
        "Identify county-pairs for comparison. Filter based on how similar counties area."
        " The goal is to identify counties that are similar in every way except for 1990 k-12 per-pupil deflated education spending."
        " We want to see county-pairs where high-spenders outperform low-spenders."
        " Use 2000-2022 non-college employment growth (emp) and wage-growth (wage) as outcome metrics."
    )


def render_pair_filters(pool):
    has_sim = any(variable in pool.columns for variable in CONT_SIM_VARS)
    has_rucc = "RUCC_2013" in pool.columns
    st.markdown(f"**Pool:** {len(pool)} counties after base filters.")

    st.subheader("General Filters")
    col1, col2, _ = st.columns(3)
    with col1:
        has_shock = "d_m_usdev82000_2011" in pool.columns
        shock_values = (
            pool["d_m_usdev82000_2011"].dropna()
            if has_shock
            else pd.Series([0.0, 5.0])
        )
        min_shock = (
            st.slider(
                "Min import shock 2000–2011 (median =0.6)",
                min_value=0.0,
                max_value=float(shock_values.max()),
                value=1.0,
                step=0.1,
                disabled=not has_shock,
                help="Not available in this dataset." if not has_shock else "",
            )
            if has_shock
            else None
        )
    with col2:
        recovery_filter = st.multiselect(
            "Recovery type (high spender)",
            options=["both", "emp", "inc", "loss"],
            default=["both", "emp", "inc", "loss"],
        )

    if "workagepop_1990" in pool.columns:
        population_values = pool["workagepop_1990"].dropna().astype(int)
        population_min = int(population_values.min())
        population_max = int(population_values.max())
        pop_col1, pop_col2 = st.columns(2)
        with pop_col1:
            pop_min = st.number_input(
                "Min working-age population (1990)",
                value=population_min,
                step=1000,
            )
        with pop_col2:
            pop_max = st.number_input(
                "Max working-age population (1990)",
                value=population_max,
                step=1000,
            )
        pop_range = (int(pop_min), int(pop_max))
    else:
        pop_range = None

    st.subheader("Similarity filters")
    similarity_col1, similarity_col2 = st.columns(2)
    with similarity_col1:
        sim_pct = st.slider(
            "Max industry/education difference (percentile of each variable's distribution)",
            min_value=1,
            max_value=50,
            value=20,
            help=(
                "Each county is ranked by percentile (0–100) for mfg, services, ag, gov employment shares, "
                "and college labor force share (1990). Paired counties must be within this many percentile "
                "points of each other on every variable. Lower = tighter matching."
            ),
            disabled=not has_sim,
        )
    with similarity_col1:
        min_ppupil_diff = st.number_input(
            "Min per-pupil spending difference (1990 $)", value=300, step=50
        )
    with similarity_col2:
        require_rucc = st.checkbox(
            "Require same RUCC 2013 rural-urban classification",
            value=True,
            disabled=not has_rucc,
            help="Not available in this dataset." if not has_rucc else "",
        )

    return {
        "min_shock": min_shock,
        "min_ppupil_diff": min_ppupil_diff,
        "recovery_filter": recovery_filter,
        "sim_pct": sim_pct,
        "require_rucc": require_rucc,
        "pop_range": pop_range,
    }


def format_pair_results(pairs):
    columns = [column for column in DISPLAY_COLUMNS if column in pairs.columns]
    output = pairs[columns].rename(columns=DISPLAY_COLUMNS).copy()

    if "Spending Diff ($)" in output.columns:
        output["Spending Diff ($)"] = output["Spending Diff ($)"].round(0).astype(int)
    if "Emp Growth Diff" in output.columns:
        output["Emp Growth Diff"] = (
            (output["Emp Growth Diff"] * 100).round(2).astype(str) + "%"
        )
    if "Wage Growth Diff" in output.columns:
        output["Wage Growth Diff"] = (
            (output["Wage Growth Diff"] * 100).round(2).astype(str) + "%"
        )
    if "Pair Score" in output.columns:
        output["Pair Score"] = output["Pair Score"].round(2)
    return output


def render_pair_results(pairs):
    if len(pairs) > 0:
        st.markdown(f"**{len(pairs)} pairs** match the current filters.")
        st.dataframe(
            format_pair_results(pairs),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No pairs match the current filters. Try loosening the parameters.")


def _add_import_shock_marker(figure):
    figure.add_shape(
        type="rect",
        xref="x",
        yref="paper",
        x0=2000,
        x1=2011,
        y0=0,
        y1=1,
        fillcolor="rgba(200,100,100,0.12)",
        line_width=0,
        layer="below",
    )
    figure.add_annotation(
        x=2005.5,
        y=0,
        yref="paper",
        text="Import Shock",
        showarrow=False,
        font=dict(size=11, color="rgba(160,60,60,0.7)"),
        yanchor="bottom",
    )


def build_pair_wage_figure(ts_high, ts_low, name_high, name_low):
    figure = go.Figure()
    _add_import_shock_marker(figure)
    if "star_median" in ts_high.columns:
        figure.add_trace(
            go.Scatter(
                x=ts_high["year"],
                y=ts_high["star_median"],
                name=name_high,
                line=dict(color="#1f77b4", width=2),
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ts_low["year"],
                y=ts_low["star_median"],
                name=name_low,
                line=dict(color="#ff7f0e", width=2),
            )
        )
    figure.update_yaxes(
        tickprefix="$",
        tickformat=",.0f",
        tickfont=dict(size=15),
        title_font=dict(size=16),
    )
    figure.update_xaxes(range=[1990, 2022], tickfont=dict(size=15))
    figure.update_layout(
        title="Median Non-College Wage",
        height=480,
        margin=dict(t=90, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=16),
        ),
        font=dict(size=16),
        title_font=dict(size=20),
    )
    return figure


def build_pair_employment_figure(ts_high, ts_low, name_high, name_low):
    figure = go.Figure()
    _add_import_shock_marker(figure)
    if "star_pop" in ts_high.columns:
        figure.add_trace(
            go.Scatter(
                x=ts_high["year"],
                y=ts_high["star_pop"],
                name=name_high,
                line=dict(color="#1f77b4", width=2),
                hovertemplate="%{x}: %{y:.2f}<extra>" + name_high + "</extra>",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ts_low["year"],
                y=ts_low["star_pop"],
                name=name_low,
                line=dict(color="#ff7f0e", width=2),
                hovertemplate="%{x}: %{y:.2f}<extra>" + name_low + "</extra>",
            )
        )
    figure.update_yaxes(
        ticksuffix="%",
        title_text="Employment-Population Ratio",
        tickfont=dict(size=15),
        title_font=dict(size=16),
    )
    figure.update_xaxes(range=[1990, 2022], tickfont=dict(size=15))
    figure.update_layout(
        title="Non-College Employment-Population Ratio",
        height=480,
        margin=dict(t=90, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=16),
        ),
        font=dict(size=16),
        title_font=dict(size=20),
    )
    return figure


def calculate_drop_and_rebound(timeseries):
    post_2000 = timeseries[timeseries["year"] >= 2000].dropna(subset=["star_pop"])
    if post_2000.empty:
        return None

    value_2000 = post_2000.loc[post_2000["year"] == 2000, "star_pop"]
    value_2022 = post_2000.loc[post_2000["year"] == 2022, "star_pop"]
    if value_2000.empty or value_2022.empty:
        return None

    start = value_2000.iloc[0]
    end = value_2022.iloc[0]
    trough = post_2000["star_pop"].min()
    trough_year = post_2000.loc[post_2000["star_pop"].idxmin(), "year"]
    return {
        "value_2000": start,
        "value_2022": end,
        "trough": trough,
        "trough_year": trough_year,
        "drop": trough - start,
        "rebound": end - trough,
        "net_change": end - start,
    }


def render_drop_and_rebound(ts_high, ts_low, name_high, name_low):
    if "star_pop" not in ts_high.columns or "star_pop" not in ts_low.columns:
        return

    st.divider()
    st.markdown("#### Non-College Employment-Population: Drop & Rebound")
    col_high, col_low = st.columns(2)
    for column, timeseries, name in [
        (col_high, ts_high, name_high),
        (col_low, ts_low, name_low),
    ]:
        values = calculate_drop_and_rebound(timeseries)
        if values is None:
            continue
        with column:
            st.markdown(f"**{name}**")
            st.markdown(
                f"- **2000 value:** {values['value_2000']:.2f}  \n"
                f"- **Trough:** {values['trough']:.2f} (year {values['trough_year']})  \n"
                f"- **Drop (2000 → trough):** {values['drop']:+.2f}  \n"
                f"- **Rebound (trough → 2022):** {values['rebound']:+.2f}  \n"
                f"- **Net change (2000 → 2022):** {values['net_change']:+.2f}"
            )


def render_spending_metrics(selected_pair, name_high, name_low):
    if (
        "ppupil_deflate1990_H" not in selected_pair
        or "ppupil_deflate1990_L" not in selected_pair
    ):
        return

    col_high, col_low = st.columns(2)
    with col_high:
        st.metric(
            f"{name_high} — Per-Pupil Spending (1990)",
            f"${round(selected_pair['ppupil_deflate1990_H']):,}",
        )
    with col_low:
        st.metric(
            f"{name_low} — Per-Pupil Spending (1990)",
            f"${round(selected_pair['ppupil_deflate1990_L']):,}",
        )


def render_pair_comparison(pairs, timeseries):
    if pairs.empty or "county_name_H" not in pairs.columns:
        return

    st.divider()
    st.subheader("County comparison over time")
    pair_labels = [
        f"{row['county_name_H']} vs {row['county_name_L']} ({row.get('state_H', '')})"
        for _, row in pairs.iterrows()
    ]
    selected_label = st.selectbox(
        "Select a pair to inspect", pair_labels, key="pair_select"
    )
    selected_pair = pairs.iloc[pair_labels.index(selected_label)]

    id_high = int(selected_pair["countyid_H"])
    id_low = int(selected_pair["countyid_L"])
    name_high = selected_pair["county_name_H"]
    name_low = selected_pair["county_name_L"]
    ts_high = timeseries[timeseries["countyid"] == id_high].sort_values("year")
    ts_low = timeseries[timeseries["countyid"] == id_low].sort_values("year")

    st.plotly_chart(
        build_pair_wage_figure(ts_high, ts_low, name_high, name_low),
        use_container_width=True,
        key="pair_wage_chart",
    )
    st.plotly_chart(
        build_pair_employment_figure(ts_high, ts_low, name_high, name_low),
        use_container_width=True,
        key="pair_emp_chart",
    )
    render_drop_and_rebound(ts_high, ts_low, name_high, name_low)
    render_spending_metrics(selected_pair, name_high, name_low)
