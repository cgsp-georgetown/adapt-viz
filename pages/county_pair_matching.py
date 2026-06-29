import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="County Pair Matching", layout="wide")

WIDE_DTA  = "county_all_vars_wide.dta"
LONG_CSV  = "county_all_vars_long.csv"
SIM_DTA   = r"county_similarity_matrix.dta"

CONT_SIM_VARS = [
    "mfg_empsh", "ag_empsh", "gov_empsh", "college_lf_share_1990",
]


@st.cache_data
def load_timeseries():
    long = pd.read_csv(LONG_CSV)
    long = long[long["year"].between(1990, 2022)].copy()
    long["year"] = long["year"].astype(int)
    keep = ["countyid", "county_name", "year", "star_median", "star_pop"]
    keep = [c for c in keep if c in long.columns]
    keep = [c for c in keep if c in long.columns]
    return long[keep].dropna(subset=["year"])


@st.cache_data
def load_pool():
    # ── Wide: cross-sectional vars ────────────────────────────────────────
    wide = pd.read_stata(WIDE_DTA)

    ppupil_col = next(
        (c for c in ["ppupil_deflate_1990", "ppupil_deflate1990", "ppupil1990",
                     "spend_ppupil_1990", "ppupil_deflate_2022"]
         if c in wide.columns),
        None
    )
    shock_col = next(
        (c for c in ["d_m_usdev82000_2011", "d_m_usdev8_2000_2011"] if c in wide.columns),
        None
    )

    wide_keep = ["countyid", "statefips", "state"]
    if ppupil_col:   wide_keep.append(ppupil_col)
    if shock_col:    wide_keep.append(shock_col)
    wide_keep = [c for c in wide_keep if c in wide.columns]
    wide = wide[wide_keep].copy()
    if ppupil_col and ppupil_col != "ppupil_deflate1990":
        wide = wide.rename(columns={ppupil_col: "ppupil_deflate1990"})
    if shock_col and shock_col != "d_m_usdev82000_2011":
        wide = wide.rename(columns={shock_col: "d_m_usdev82000_2011"})

    # ── Long: time-series vars pivoted ───────────────────────────────────
    long = pd.read_csv(LONG_CSV)
    long = long[long["year"].isin([1990, 2000, 2011, 2022])].copy()
    long["year"] = long["year"].astype(int)

    ts_cols = ["countyid", "county_name", "year",
               "workagepop", "totalSTARS", "employed_STARs",
               "star_median", "mfgsh", "star_emp_rate"]
    ts_cols = [c for c in ts_cols if c in long.columns]

    piv = long[ts_cols].pivot_table(
        index=["countyid", "county_name"],
        columns="year",
        values=[c for c in ts_cols if c not in ("countyid", "county_name")],
        aggfunc="first",
    )
    piv.columns = [f"{v}_{y}" for v, y in piv.columns]
    piv = piv.reset_index()

    # ── Similarity matrix ─────────────────────────────────────────────────
    sim = pd.read_stata(SIM_DTA)
    sim_keep = ["countyid"] + [c for c in CONT_SIM_VARS + ["RUCC_2013", "Description"] if c in sim.columns]
    sim = sim[sim_keep].copy()

    # ── Merge all ─────────────────────────────────────────────────────────
    df = piv.merge(wide, on="countyid", how="inner")
    df = df.merge(sim, on="countyid", how="left")


    # Derived variables
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

    df = df.dropna(subset=[
        c for c in ["ppupil_deflate1990", "d_star_med_pct_2000_2022", "d_pct_star_emp_2000_2022"]
        if c in df.columns
    ])

    def _recovery(row):
        emp = row.get("d_pct_star_emp_2000_2022", 0) > 0
        inc = row.get("d_star_med_pct_2000_2022", 0) > 0
        if emp and inc:  return "both"
        if emp:          return "emp"
        if inc:          return "inc"
        return "loss"

    df["recovery"] = df.apply(_recovery, axis=1)
    if "workagepop_1990" in df.columns:
        df["workagepop_1990"] = df["workagepop_1990"].round(0).astype("Int64")
    return df.reset_index(drop=True)


def build_pairs(pool, min_shock, min_ppupil_diff,
                recovery_filter, sim_pct, require_rucc, pop_range=None):
    sub = pool.copy()
    if min_shock is not None and "d_m_usdev82000_2011" in sub.columns:
        sub = sub[sub["d_m_usdev82000_2011"] >= min_shock]
    if pop_range is not None and "workagepop_1990" in sub.columns:
        sub = sub[sub["workagepop_1990"].between(pop_range[0], pop_range[1])]

    # Convert each similarity variable to its percentile rank (0–100) across the pool
    for v in CONT_SIM_VARS:
        if v in sub.columns:
            sub[f"{v}_pct"] = sub[v].rank(pct=True) * 100

    a = sub.add_suffix("_A").assign(_key=1)
    b = sub.add_suffix("_B").assign(_key=1)
    pairs = a.merge(b, on="_key").drop(columns="_key")

    pairs = pairs[pairs["statefips_A"] == pairs["statefips_B"]]
    pairs = pairs[pairs["countyid_A"] < pairs["countyid_B"]]

    # RUCC must match
    if require_rucc and "RUCC_2013_A" in pairs.columns:
        pairs = pairs[pairs["RUCC_2013_A"] == pairs["RUCC_2013_B"]]

    # Keep pairs within sim_pct percentile points on every similarity variable
    for v in CONT_SIM_VARS:
        col_a, col_b = f"{v}_pct_A", f"{v}_pct_B"
        if col_a in pairs.columns and col_b in pairs.columns:
            pairs = pairs[(pairs[col_a] - pairs[col_b]).abs() <= sim_pct]

    if "ppupil_deflate1990_A" not in pairs.columns:
        st.error("ppupil_deflate1990 not found — cannot compute spending difference.")
        return pd.DataFrame()

    pairs["ppupil_diff_raw"] = pairs["ppupil_deflate1990_A"] - pairs["ppupil_deflate1990_B"]
    pairs = pairs[pairs["ppupil_diff_raw"].abs() >= min_ppupil_diff]

    pairs["aligns_A"] = (
        (pairs["ppupil_diff_raw"] > 0) &
        (pairs["d_pct_star_emp_2000_2022_A"] > pairs["d_pct_star_emp_2000_2022_B"]) &
        (pairs["d_star_med_pct_2000_2022_A"] > pairs["d_star_med_pct_2000_2022_B"])
    )
    pairs["aligns_B"] = (
        (pairs["ppupil_diff_raw"] < 0) &
        (pairs["d_pct_star_emp_2000_2022_B"] > pairs["d_pct_star_emp_2000_2022_A"]) &
        (pairs["d_star_med_pct_2000_2022_B"] > pairs["d_star_med_pct_2000_2022_A"])
    )
    pairs = pairs[pairs["aligns_A"] | pairs["aligns_B"]].copy()

    hvars = [
        "countyid", "county_name", "state", "workagepop_1990", "ppupil_deflate1990",
        "d_star_med_pct_2000_2022", "d_pct_star_emp_2000_2022", "recovery",
        "totalSTARS_1990", "star_median_2000", "star_median_2022",
        "employed_STARs_2000", "employed_STARs_2022",
        "star_emp_rate_1990", "star_emp_rate_2011", "star_emp_rate_2022",
        "d_mfg_job_pct_1990_2011", "d_m_usdev82000_2011",
        "RUCC_2013", "Description",
    ] + CONT_SIM_VARS
    hvars = [v for v in hvars if v + "_A" in pairs.columns]

    for v in hvars:
        pairs[v + "_H"] = pairs.apply(
            lambda r, _v=v: r[_v + "_A"] if r["aligns_A"] else r[_v + "_B"], axis=1
        )
        pairs[v + "_L"] = pairs.apply(
            lambda r, _v=v: r[_v + "_B"] if r["aligns_A"] else r[_v + "_A"], axis=1
        )

    pairs["d_ppupil"]      = pairs["ppupil_deflate1990_H"] - pairs["ppupil_deflate1990_L"]
    pairs["d_wage_growth"] = pairs["d_star_med_pct_2000_2022_H"] - pairs["d_star_med_pct_2000_2022_L"]
    pairs["d_emp_growth"]  = pairs["d_pct_star_emp_2000_2022_H"] - pairs["d_pct_star_emp_2000_2022_L"]
    pairs["pair_score"]    = (
        (pairs["d_ppupil"] / 100)
        + (pairs["d_wage_growth"] * 10)
        + (pairs["d_emp_growth"] * 10)
    )
    if "d_m_usdev82000_2011_H" in pairs.columns and "d_m_usdev82000_2011_L" in pairs.columns:
        pairs["pair_score"] -= (
            pairs["d_m_usdev82000_2011_H"] - pairs["d_m_usdev82000_2011_L"]
        ).abs()

    if "recovery_H" in pairs.columns:
        pairs = pairs[pairs["recovery_H"].isin(recovery_filter)]

    return pairs.sort_values("pair_score", ascending=False).reset_index(drop=True)


# ── UI ──────────────────────────────────────────────────────────────────────

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
