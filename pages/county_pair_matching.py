import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dashboard_lib.pair_matching import (
    CONT_SIM_VARS,
    build_pairs,
    load_pool,
    load_timeseries,
)

st.set_page_config(page_title="County Pair Matching", layout="wide")


st.title("County Pair Matching")
st.caption(
    "Identify county-pairs for comparison. Filter based on how similar counties area." \
    " The goal is to identify counties that are similar in every way except for 1990 k-12 per-pupil deflated education spending." \
    " We want to see county-pairs where high-spenders outperform low-spenders." \
    " Use 2000-2022 non-college employment growth (emp) and wage-growth (wage) as outcome metrics."
)

pool = load_pool()

has_sim = any(v in pool.columns for v in CONT_SIM_VARS)
has_rucc = "RUCC_2013" in pool.columns
st.markdown(f"**Pool:** {len(pool)} counties after base filters.")

st.subheader("General Filters")
col1, col2, col3 = st.columns(3)
with col1:
    has_shock = "d_m_usdev82000_2011" in pool.columns
    _shock_vals = pool["d_m_usdev82000_2011"].dropna() if has_shock else pd.Series([0.0, 5.0])
    min_shock = st.slider(
        "Min import shock 2000–2011 (median =0.6)",
        min_value=0.0,
        max_value=float(_shock_vals.max()),
        value=1.0,
        step=0.1,
        disabled=not has_shock,
        help="Not available in this dataset." if not has_shock else "",
    ) if has_shock else None
with col2:
    recovery_filter = st.multiselect(
        "Recovery type (high spender)",
        options=["both", "emp", "inc", "loss"],
        default=["both", "emp", "inc", "loss"],
    )

if "workagepop_1990" in pool.columns:
    _pop_vals = pool["workagepop_1990"].dropna().astype(int)
    _pop_min, _pop_max = int(_pop_vals.min()), int(_pop_vals.max())
    _pc1, _pc2 = st.columns(2)
    with _pc1:
        pop_min = st.number_input("Min working-age population (1990)", value=_pop_min, step=1000)
    with _pc2:
        pop_max = st.number_input("Max working-age population (1990)", value=_pop_max, step=1000)
    pop_range = (int(pop_min), int(pop_max))
else:
    pop_range = None

st.subheader("Similarity filters")
sc1, sc2 = st.columns(2)
with sc1:
    sim_pct = st.slider(
        "Max industry/education difference (percentile of each variable's distribution)",
        min_value=1, max_value=50, value=20,
        help=(
            "Each county is ranked by percentile (0–100) for mfg, services, ag, gov employment shares, "
            "and college labor force share (1990). Paired counties must be within this many percentile "
            "points of each other on every variable. Lower = tighter matching."
        ),
        disabled=not has_sim,
    )
with sc1:
    min_ppupil_diff = st.number_input(
        "Min per-pupil spending difference (1990 $)", value=300, step=50
    )
with sc2:
    require_rucc = st.checkbox(
        "Require same RUCC 2013 rural-urban classification",
        value=True,
        disabled=not has_rucc,
        help="Not available in this dataset." if not has_rucc else "",
    )

pairs = build_pairs(
    pool, min_shock, min_ppupil_diff,
    recovery_filter, sim_pct, require_rucc, pop_range,
)

if isinstance(pairs, pd.DataFrame) and len(pairs) > 0:
    st.markdown(f"**{len(pairs)} pairs** match the current filters.")

    display_cols = {
        "state_H":                  "State",
        "county_name_H":            "High Spender",
        "county_name_L":            "Low Spender",
        "Description_H":            "RUCC Description",
        "d_ppupil":                 "Spending Diff ($)",
        "d_emp_growth":             "Emp Growth Diff",
        "d_wage_growth":            "Wage Growth Diff",
        "recovery_H":               "Recovery (H)",
        "recovery_L":               "Recovery (L)",
        "workagepop_1990_H":        "Work-Age Pop 1990 (H)",
        "workagepop_1990_L":        "Work-Age Pop 1990 (L)",
        "ppupil_deflate1990_H":     "Per-Pupil 1990 (H)",
        "ppupil_deflate1990_L":     "Per-Pupil 1990 (L)",
        "d_m_usdev82000_2011_H":    "Shock (H)",
        "d_m_usdev82000_2011_L":    "Shock (L)",
        "star_median_2000_H":       "NC Wage 2000 (H)",
        "star_median_2022_H":       "NC Wage 2022 (H)",
        "star_median_2000_L":       "NC Wage 2000 (L)",
        "star_median_2022_L":       "NC Wage 2022 (L)",
        "mfg_empsh_H":              "Mfg Emp Share (H)",
        "mfg_empsh_L":              "Mfg Emp Share (L)",
        "college_lf_share_1990_H":  "College LF Share 1990 (H)",
        "college_lf_share_1990_L":  "College LF Share 1990 (L)",
        "pair_score":               "Pair Score",
    }
    show = [c for c in display_cols if c in pairs.columns]
    out = pairs[show].rename(columns=display_cols).copy()

    if "Spending Diff ($)" in out.columns:
        out["Spending Diff ($)"] = out["Spending Diff ($)"].round(0).astype(int)
    if "Emp Growth Diff" in out.columns:
        out["Emp Growth Diff"] = (out["Emp Growth Diff"] * 100).round(2).astype(str) + "%"
    if "Wage Growth Diff" in out.columns:
        out["Wage Growth Diff"] = (out["Wage Growth Diff"] * 100).round(2).astype(str) + "%"
    if "Pair Score" in out.columns:
        out["Pair Score"] = out["Pair Score"].round(2)

    st.dataframe(out, use_container_width=True, hide_index=True)
elif isinstance(pairs, pd.DataFrame):
    st.info("No pairs match the current filters. Try loosening the parameters.")

if isinstance(pairs, pd.DataFrame) and len(pairs) > 0 and "county_name_H" in pairs.columns:
    st.divider()
    st.subheader("County comparison over time")

    pair_labels = [
        f"{row['county_name_H']} vs {row['county_name_L']} ({row.get('state_H', '')})"
        for _, row in pairs.iterrows()
    ]
    selected_label = st.selectbox("Select a pair to inspect", pair_labels, key="pair_select")
    sel_idx = pair_labels.index(selected_label)
    sel = pairs.iloc[sel_idx]

    id_h = int(sel["countyid_H"])
    id_l = int(sel["countyid_L"])
    name_h = sel["county_name_H"]
    name_l = sel["county_name_L"]

    ts = load_timeseries()
    ts_h = ts[ts["countyid"] == id_h].sort_values("year")
    ts_l = ts[ts["countyid"] == id_l].sort_values("year")

    shock_shape = dict(
        type="rect", xref="x", yref="paper",
        x0=2000, x1=2011, y0=0, y1=1,
        fillcolor="rgba(200,100,100,0.12)", line_width=0,
        layer="below",
    )
    # ── Wage chart ────────────────────────────────────────────────────────
    fig1 = go.Figure()
    fig1.add_shape(**shock_shape)
    fig1.add_annotation(
        x=2005.5, y=0, yref="paper", text="Import Shock",
        showarrow=False, font=dict(size=11, color="rgba(160,60,60,0.7)"),
        yanchor="bottom",
    )
    if "star_median" in ts_h.columns:
        fig1.add_trace(go.Scatter(
            x=ts_h["year"], y=ts_h["star_median"],
            name=name_h, line=dict(color="#1f77b4", width=2),
        ))
        fig1.add_trace(go.Scatter(
            x=ts_l["year"], y=ts_l["star_median"],
            name=name_l, line=dict(color="#ff7f0e", width=2),
        ))
    fig1.update_yaxes(tickprefix="$", tickformat=",.0f", tickfont=dict(size=15), title_font=dict(size=16))
    fig1.update_xaxes(range=[1990, 2022], tickfont=dict(size=15))
    fig1.update_layout(
        title="Median Non-College Wage",
        height=480, margin=dict(t=90, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=16)),
        font=dict(size=16),
        title_font=dict(size=20),
    )
    st.plotly_chart(fig1, use_container_width=True, key="pair_wage_chart")

    # ── Employment-population ratio chart ─────────────────────────────────
    fig2 = go.Figure()
    fig2.add_shape(**shock_shape)
    fig2.add_annotation(
        x=2005.5, y=0, yref="paper", text="Import Shock",
        showarrow=False, font=dict(size=11, color="rgba(160,60,60,0.7)"),
        yanchor="bottom",
    )
    if "star_pop" in ts_h.columns:
        fig2.add_trace(go.Scatter(
            x=ts_h["year"], y=ts_h["star_pop"],
            name=name_h, line=dict(color="#1f77b4", width=2),
            hovertemplate="%{x}: %{y:.2f}<extra>" + name_h + "</extra>",
        ))
        fig2.add_trace(go.Scatter(
            x=ts_l["year"], y=ts_l["star_pop"],
            name=name_l, line=dict(color="#ff7f0e", width=2),
            hovertemplate="%{x}: %{y:.2f}<extra>" + name_l + "</extra>",
        ))
    fig2.update_yaxes(ticksuffix="%", title_text="Employment-Population Ratio", tickfont=dict(size=15), title_font=dict(size=16))
    fig2.update_xaxes(range=[1990, 2022], tickfont=dict(size=15))
    fig2.update_layout(
        title="Non-College Employment-Population Ratio",
        height=480, margin=dict(t=90, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=16)),
        font=dict(size=16),
        title_font=dict(size=20),
    )
    st.plotly_chart(fig2, use_container_width=True, key="pair_emp_chart")

    # Drop & rebound in star_pop
    if "star_pop" in ts_h.columns and "star_pop" in ts_l.columns:
        st.divider()
        st.markdown("#### Non-College Employment-Population: Drop & Rebound")
        dc1, dc2 = st.columns(2)
        for col, ts, name in [(dc1, ts_h, name_h), (dc2, ts_l, name_l)]:
            ts_post = ts[ts["year"] >= 2000].dropna(subset=["star_pop"])
            if len(ts_post) == 0:
                continue
            val_2000 = ts_post.loc[ts_post["year"] == 2000, "star_pop"]
            val_2022 = ts_post.loc[ts_post["year"] == 2022, "star_pop"]
            if val_2000.empty or val_2022.empty:
                continue
            v2000 = val_2000.iloc[0]
            v2022 = val_2022.iloc[0]
            min_val = ts_post["star_pop"].min()
            min_year = ts_post.loc[ts_post["star_pop"].idxmin(), "year"]
            drop = min_val - v2000
            rebound = v2022 - min_val
            with col:
                st.markdown(f"**{name}**")
                st.markdown(
                    f"- **2000 value:** {v2000:.2f}  \n"
                    f"- **Trough:** {min_val:.2f} (year {min_year})  \n"
                    f"- **Drop (2000 → trough):** {drop:+.2f}  \n"
                    f"- **Rebound (trough → 2022):** {rebound:+.2f}  \n"
                    f"- **Net change (2000 → 2022):** {v2022 - v2000:+.2f}"
                )

    # Per-pupil spending 1990
    if "ppupil_deflate1990_H" in sel and "ppupil_deflate1990_L" in sel:
        mc1, mc2 = st.columns(2)
        with mc1:
            st.metric(f"{name_h} — Per-Pupil Spending (1990)", f"${round(sel['ppupil_deflate1990_H']):,}")
        with mc2:
            st.metric(f"{name_l} — Per-Pupil Spending (1990)", f"${round(sel['ppupil_deflate1990_L']):,}")
