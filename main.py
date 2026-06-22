"""
Created on Tue Oct 17 15:17:06 2023

@author: joshu
"""

## This code creates a Streamlit dashboard for county economic data, allowing users to select a state and county to view various economic metrics and trends.

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import math
import json
from urllib.request import urlopen

st.set_page_config(page_title="Hello", page_icon="🚚",layout='wide')
streamlit_style = """
			<style>
			@import url('https://fonts.googleapis.com/css2?family=Roboto, sans-serif:wght@100&display=swap');

			html, body, [class*="css"]  {
			font-family: 'Roboto, sans-serif', sans-serif;
			}
			</style>
			"""
st.markdown(streamlit_style, unsafe_allow_html=True)


### initialize all inputs/variables

@st.cache_data  # This function will be cached to optimize loading
def load_data():
    path1 = "county_all_vars_wide.dta"
    path2 = "county_all_vars_long.dta"
    path3 = "cbp_county_2016.csv"
    path4 = "cbp_county_2016_all_tradserv_emp.csv"
    return pd.read_stata(path1), pd.read_stata(path2), pd.read_csv(path3), pd.read_csv(path4)

@st.cache_data
def load_grad_data():
    df = pd.read_stata("county_panel_90001122.dta")
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

national_df, long_df, cbp_df, tradserv_df = load_data()
grad_df = load_grad_data()

_grad_map_cols = grad_df[["county_fips", "total_fouryear_grads_2022", "total_subba_grads_2022"]].copy()
_grad_map_cols["county_fips"] = _grad_map_cols["county_fips"].astype(float)
national_df = national_df.merge(_grad_map_cols, left_on="countyid", right_on="county_fips", how="left").drop(columns="county_fips")
national_df["total_fouryear_grads_2022"] = national_df["total_fouryear_grads_2022"].fillna(0)
national_df["total_subba_grads_2022"]    = national_df["total_subba_grads_2022"].fillna(0)
_wap_col = next((c for c in ["total_workers2022", "total_workers", "employed_workers_2022"] if c in national_df.columns), None)
if _wap_col:
    national_df["fouryear_grads_per_wap_2022"] = national_df["total_fouryear_grads_2022"] / national_df[_wap_col].replace(0, float("nan"))
    national_df["subba_grads_per_wap_2022"]    = national_df["total_subba_grads_2022"]    / national_df[_wap_col].replace(0, float("nan"))
else:
    national_df["fouryear_grads_per_wap_2022"] = float("nan")
    national_df["subba_grads_per_wap_2022"]    = float("nan")

# Remove CT planning regions (Census added these in 2022; not traditional counties)
_ct_planning = national_df["county_name"].str.contains("Planning Region", case=False, na=False)
national_df = national_df[~_ct_planning].copy()
_ct_planning_long = long_df["county_name"].str.contains("Planning Region", case=False, na=False)
long_df = long_df[~_ct_planning_long].copy()

wide_df = national_df.copy()   # unfiltered wide data for national maps

# Population quintile (5 groups) from workagepop for finer-grained peer comparisons
if "workagepop" in wide_df.columns:
    wide_df["qpop5"] = pd.qcut(
        wide_df["workagepop"], q=5,
        labels=["Quintile 1 (Smallest)", "Quintile 2", "Quintile 3",
                "Quintile 4", "Quintile 5 (Largest)"],
        duplicates="drop",
    )
else:
    wide_df["qpop5"] = wide_df["qpop"]  # fallback to quartile

# Pre-compute tradable services share of employment (2016) for all counties
_total_emp_all    = cbp_df.groupby("countyid")["emp"].sum().rename("_total_emp_2016")
_tradserv_emp_all = tradserv_df.groupby("countyid")["emp"].sum().rename("_tradserv_emp_2016")
_tradserv_share   = (_tradserv_emp_all / _total_emp_all.replace(0, float("nan")) * 100).rename("tradserv_pct_2016")
wide_df = wide_df.merge(_tradserv_share, left_on="countyid", right_index=True, how="left")
wide_df = wide_df.merge(_total_emp_all, left_on="countyid", right_index=True, how="left")
wide_df["_total_emp_2016"] = wide_df["_total_emp_2016"].replace(0, float("nan"))
if "tradserv_exp_emp_2017_2022" in wide_df.columns and "_total_emp_2016" in wide_df.columns:
    wide_df["tradserv_exp_pct_2016emp"] = (
        wide_df["tradserv_exp_emp_2017_2022"].astype(float)
        / wide_df["_total_emp_2016"].astype(float)
        * 100
    )
else:
    wide_df["tradserv_exp_pct_2016emp"] = float("nan")

# % STARs in middle/upper income jobs (2022) from long panel
if "pct_star_midupp" in long_df.columns:
    _midupp_2022 = (
        long_df[long_df["year"] == 2022]
        .drop_duplicates(subset=["countyid"])[["countyid", "pct_star_midupp"]]
        .rename(columns={"pct_star_midupp": "pct_star_midupp_2022"})
    )
    wide_df = wide_df.merge(_midupp_2022, on="countyid", how="left")

default_state = "CA"
default_county = "Los Angeles County, CA"

sorted_states = np.sort(national_df['state'].unique())
try:
    default_index_st = int(np.where(sorted_states == default_state)[0][0])
except IndexError:
    default_index_st = 0

# -----------------------------
# State label constants & helpers
# -----------------------------
_STATE_NAME = {
    "01":"Alabama","04":"Arizona","05":"Arkansas","06":"California","08":"Colorado",
    "09":"Connecticut","10":"Delaware","12":"Florida","13":"Georgia",
    "16":"Idaho","17":"Illinois","18":"Indiana","19":"Iowa","20":"Kansas","21":"Kentucky",
    "22":"Louisiana","23":"Maine","24":"Maryland","25":"Massachusetts","26":"Michigan","27":"Minnesota",
    "28":"Mississippi","29":"Missouri","30":"Montana","31":"Nebraska","32":"Nevada","33":"New Hampshire",
    "34":"New Jersey","35":"New Mexico","36":"New York","37":"North Carolina","38":"North Dakota",
    "39":"Ohio","40":"Oklahoma","41":"Oregon","42":"Pennsylvania","44":"Rhode Island","45":"South Carolina",
    "46":"South Dakota","47":"Tennessee","48":"Texas","49":"Utah","50":"Vermont","51":"Virginia",
    "53":"Washington","54":"West Virginia","55":"Wisconsin","56":"Wyoming",
}
_STATE_USPS = {
    "01":"AL","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE",
    "12":"FL","13":"GA","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY",
    "22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS","29":"MO",
    "30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC",
    "38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD",
    "47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV","55":"WI","56":"WY",
}
_NEW_ENGLAND  = {"33","50","25","44","09"}   # NH, VT, MA, RI, CT
_SMALL_STATES = {"10","24","34"}             # DE, MD, NJ
_EXCLUDE_FP   = {"02","15","60","66","69","72","78"}

# Approximate state label centroids (lat, lon)
_STATE_LABEL_POS = {
    "01":(32.8, -86.8), "04":(34.3,-111.1), "05":(34.9, -92.4), "06":(37.2,-119.4),
    "08":(39.0,-105.5), "09":(41.6, -72.7), "10":(39.0, -75.5), "12":(28.1, -81.6),
    "13":(32.6, -83.4), "16":(44.4,-114.6), "17":(40.0, -89.2), "18":(39.9, -86.3),
    "19":(42.1, -93.5), "20":(38.5, -98.4), "21":(37.5, -85.3), "22":(31.1, -92.0),
    "23":(45.4, -69.2), "24":(39.0, -76.8), "25":(42.3, -71.8), "26":(44.3, -85.4),
    "27":(46.4, -93.3), "28":(32.7, -89.7), "29":(38.4, -92.5), "30":(47.0,-110.0),
    "31":(41.5, -99.7), "32":(39.3,-117.1), "33":(43.7, -71.6), "34":(40.1, -74.5),
    "35":(34.5,-106.1), "36":(42.9, -75.6), "37":(35.5, -79.4), "38":(47.5,-100.5),
    "39":(40.4, -82.8), "40":(35.6, -97.5), "41":(44.1,-120.5), "42":(40.9, -77.8),
    "44":(41.7, -71.5), "45":(33.9, -80.9), "46":(44.4, -99.9), "47":(35.9, -86.4),
    "48":(31.5, -99.3), "49":(39.3,-111.1), "50":(44.0, -72.7), "51":(37.5, -78.9),
    "53":(47.4,-120.4), "54":(38.6, -80.6), "55":(44.6, -89.9), "56":(43.0,-107.6),
}

def _state_label_trace():
    """Permanent Scattergeo text trace with state names/abbreviations."""
    lats, lons, texts = [], [], []
    for fips, (lat, lon) in _STATE_LABEL_POS.items():
        lats.append(lat); lons.append(lon)
        if fips in _NEW_ENGLAND or fips in _SMALL_STATES:
            texts.append(_STATE_USPS.get(fips, ""))
        else:
            texts.append(_STATE_NAME.get(fips, ""))
    return go.Scattergeo(
        lat=lats, lon=lons,
        mode="text",
        text=texts,
        textfont=dict(size=7, color="black", family="Roboto, sans-serif"),
        hoverinfo="skip",
        showlegend=False,
        visible=True,
    )

_GEO_CONUS = dict(
    projection_type="albers usa",
    showlakes=False, showframe=False, bgcolor="white",
    lataxis=dict(range=[24, 50]),
    lonaxis=dict(range=[-125, -66]),
    showland=True, landcolor="#f5f5f5",
    showcoastlines=False,
    showsubunits=True, subunitcolor="white", subunitwidth=0.8,
)

# -----------------------------
# National qpotential map
# -----------------------------
@st.cache_data
def load_counties_geojson():
    with urlopen("https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json") as response:
        return json.load(response)

@st.cache_data
def get_county_centroids():
    """Compute mean lat/lon centroid for each county from the geojson."""
    geo = load_counties_geojson()
    out = {}
    for feat in geo["features"]:
        fips = feat["id"]
        gtype = feat["geometry"]["type"]
        coords = feat["geometry"]["coordinates"]
        pts = []
        if gtype == "Polygon":
            for ring in coords: pts.extend(ring)
        elif gtype == "MultiPolygon":
            for poly in coords:
                for ring in poly: pts.extend(ring)
        if pts:
            out[fips] = (sum(p[1] for p in pts) / len(pts),
                         sum(p[0] for p in pts) / len(pts))
    return out

@st.cache_data
def build_national_map(long_df_hash):
    _EXCLUDE = {"02", "15", "60", "66", "69", "72", "78"}
    _Q_COLORS = {1: "#F76B47", 2: "#FEBC7F", 3: "#FEE59C", 4: "#b2abd2", 5: "#8073ac"}
    _Q_LABELS = {
        1: "Far below Potential", 2: "Below Potential", 3: "Median",
        4: "Close to Potential",  5: "Potential Reached",
    }
    _QPOP_ORDER = [
        "Most populated quartile (by people)",
        "2nd most populated quartile (by people)",
        "3rd most populated quartile (by people)",
        "4th most populated quartile (by people)",
    ]
    _QPOP_SHORT = {
        "Most populated quartile (by people)":     "Most Populated (Q1)",
        "2nd most populated quartile (by people)": "2nd Most Populated (Q2)",
        "3rd most populated quartile (by people)": "3rd Most Populated (Q3)",
        "4th most populated quartile (by people)": "Least Populated (Q4)",
    }

    df = long_df_hash.copy()
    df["fips"] = df["countyid"].astype(float).astype(int).astype(str).str.zfill(5)
    df["qpotential"] = pd.to_numeric(df["qpotential"], errors="coerce")
    df = df[~df["fips"].str[:2].isin(_EXCLUDE)].copy()

    def fmt_rate(v):
        try:
            return f"{float(v):.1f}%"
        except Exception:
            return "N/A"

    df["hover"] = (
        "<b>" + df["county_name"].fillna("") + "</b><br>"
        + "Population Quartile: " + df["qpop"].map(_QPOP_SHORT).fillna("") + "<br>"
        + "Potential Quintile: " + df["qpotential"].map(
            lambda x: f"{int(x)} – {_Q_LABELS.get(int(x), '')}" if pd.notna(x) else "N/A"
        ) + "<br>"
        + "Employment Rate: " + df["employment_rate_2022"].apply(fmt_rate) + "<br>"
        + "Non-College Emp Rate: " + df["star_emp_rate_2022"].apply(fmt_rate)
    )

    counties_geojson = load_counties_geojson()
    all_groups = ["All"] + _QPOP_ORDER
    traces = []

    for group in all_groups:
        subset = df if group == "All" else df[df["qpop"] == group]
        for q in [1, 2, 3, 4, 5]:
            sub_q = subset[subset["qpotential"] == q]
            traces.append(go.Choropleth(
                geojson=counties_geojson,
                locations=sub_q["fips"],
                z=[q] * len(sub_q),
                zmin=1, zmax=5,
                colorscale=[[0, _Q_COLORS[q]], [1, _Q_COLORS[q]]],
                showscale=False,
                marker_line_width=0.15,
                marker_line_color="white",
                hovertext=sub_q["hover"],
                hoverinfo="text",
                showlegend=False,
                visible=(group == "All"),
            ))
        sub_na = subset[subset["qpotential"].isna()]
        traces.append(go.Choropleth(
            geojson=counties_geojson,
            locations=sub_na["fips"],
            z=[0] * len(sub_na),
            zmin=0, zmax=0,
            colorscale=[[0, "#d9d9d9"], [1, "#d9d9d9"]],
            showscale=False,
            marker_line_width=0.15,
            marker_line_color="white",
            hovertext=sub_na["county_name"].fillna("") + "<br>No data",
            hoverinfo="text",
            showlegend=False,
            visible=(group == "All"),
        ))

    # Permanent dummy traces for legend — always visible regardless of dropdown
    legend_items = list(_Q_LABELS.items()) + [("nd", "No Data")]
    legend_colors = [_Q_COLORS.get(q, "#d9d9d9") for q, _ in legend_items]
    for (q, label), color in zip(legend_items, legend_colors):
        traces.append(go.Scattergeo(
            lat=[None], lon=[None],
            mode="markers",
            marker=dict(size=14, color=color, symbol="square"),
            name=label,
            showlegend=True,
            visible=True,
        ))

    def vis_for(selected):
        choropleth_vis = [group == selected for group in all_groups for _ in range(6)]
        always_vis = [True] * len(legend_items)
        return choropleth_vis + always_vis

    buttons = [dict(
        label="All Population Quartiles" if g == "All" else _QPOP_SHORT[g],
        method="update",
        args=[{"visible": vis_for(g)}],
    ) for g in all_groups]

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text="<b>ADAPT Index — Potential Quintile (2022)</b>",
            x=0.5, xanchor="center",
            font=dict(size=18, color="black", family="Roboto, sans-serif"),
        ),
        geo=_GEO_CONUS,
        paper_bgcolor="white",
        updatemenus=[dict(
            type="dropdown", direction="down",
            x=0.01, y=0.98, xanchor="left", yanchor="top",
            showactive=True, buttons=buttons,
            bgcolor="white", bordercolor="black",
            font={"size": 12, "color": "black"},
        )],
        legend=dict(
            title=dict(text="<b>Potential Quintile</b>", font=dict(color="black", size=12)),
            x=0.82, y=0.5,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="black", borderwidth=1,
            font=dict(color="black", size=11),
        ),
        margin=dict(l=0, r=0, t=60, b=0),
        height=600,
    )
    return fig

_WAGE_METRICS = {
    "Non-College Median Wage (2022)":         ("star_wage",    "$"),
    "College Median Wage (2022)":             ("college_wage", "$"),
}

@st.cache_data
def build_wage_map(long_df_hash, metric_col):
    _EXCLUDE = {"02", "15", "60", "66", "69", "72", "78"}
    _QPOP_ORDER = [
        "Most populated quartile (by people)",
        "2nd most populated quartile (by people)",
        "3rd most populated quartile (by people)",
        "4th most populated quartile (by people)",
    ]
    _QPOP_SHORT = {
        "Most populated quartile (by people)":     "Most Populated (Q1)",
        "2nd most populated quartile (by people)": "2nd Most Populated (Q2)",
        "3rd most populated quartile (by people)": "3rd Most Populated (Q3)",
        "4th most populated quartile (by people)": "Least Populated (Q4)",
    }

    df = long_df_hash[long_df_hash["year"] == 2022].drop_duplicates(subset=["countyid"]).copy()
    df["fips"] = df["countyid"].astype(float).astype(int).astype(str).str.zfill(5)
    df[metric_col] = pd.to_numeric(df[metric_col], errors="coerce")
    df = df[~df["fips"].str[:2].isin(_EXCLUDE)].copy()

    col_label, prefix = next((k, p) for k, (c, p) in _WAGE_METRICS.items() if c == metric_col)
    is_dollar = prefix == "$"

    # Normalize within each qpop group (percentile rank 0–100 among peers)
    df["_norm"] = df.groupby("qpop")[metric_col].rank(pct=True) * 100

    def fmt_val(row):
        raw = row[metric_col]
        norm = row["_norm"]
        try:
            raw_str = f"${float(raw):,.0f}" if is_dollar else f"{float(raw):,.0f}"
            return f"{raw_str} (pctile within group: {float(norm):.0f})"
        except Exception:
            return "N/A"

    df["hover"] = (
        "<b>" + df["county_name"].fillna("") + "</b><br>"
        + "Population Quartile: " + df["qpop"].map(_QPOP_SHORT).fillna("") + "<br>"
        + col_label + ": " + df.apply(fmt_val, axis=1)
    )

    counties_geojson = load_counties_geojson()
    all_groups = ["All"] + _QPOP_ORDER
    traces = []

    for group in all_groups:
        subset = df if group == "All" else df[df["qpop"] == group]
        sub = subset.dropna(subset=["_norm"])
        traces.append(go.Choropleth(
            geojson=counties_geojson,
            locations=sub["fips"],
            z=sub["_norm"],
            zmin=0, zmax=100,
            colorscale="Blues",
            colorbar=dict(
                title=dict(
                    text="Percentile within group",
                    font=dict(size=11, color="black", family="Roboto, sans-serif"),
                ),
                tickfont=dict(size=10, color="black", family="Roboto, sans-serif"),
                ticksuffix="th",
                len=0.6,
            ),
            marker_line_width=0.15,
            marker_line_color="white",
            hovertext=sub["hover"],
            hoverinfo="text",
            visible=(group == "All"),
        ))

    buttons = [dict(
        label="All Population Quartiles" if g == "All" else _QPOP_SHORT[g],
        method="update",
        args=[{"visible": [grp == g for grp in all_groups]}],
    ) for g in all_groups]

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text=f"<b>{col_label} — Percentile Rank Within Population Group (2022)</b>",
            x=0.5, xanchor="center",
            font=dict(size=16, color="black", family="Roboto, sans-serif"),
        ),
        geo=_GEO_CONUS,
        paper_bgcolor="white",
        showlegend=False,
        updatemenus=[dict(
            type="dropdown", direction="down",
            x=0.01, y=0.98, xanchor="left", yanchor="top",
            showactive=True, buttons=buttons,
            bgcolor="white", bordercolor="black",
            font={"size": 12, "color": "black"},
        )],
        margin=dict(l=0, r=0, t=60, b=0),
        height=580,
    )
    return fig

_TRADE_METRICS = {
    "Est. Job Loss from Low-Wage Imports (1991–2011)":    ("pred_emp_loss",              "Reds",   ",.0f"),
    "Est. Job Gain from Exports & Inputs (2011–2022)":    ("pred_emp_gain",              "Greens", ",.0f"),
    "Tradable Services Job Growth (2017–2022)":           ("tradserv_exp_emp_2017_2022", "Blues",  ",.0f"),
}

@st.cache_data
def build_trade_map(long_df_hash, metric_col, colorscale):
    _EXCLUDE = {"02", "15", "60", "66", "69", "72", "78"}
    _QPOP_ORDER = [
        "Most populated quartile (by people)",
        "2nd most populated quartile (by people)",
        "3rd most populated quartile (by people)",
        "4th most populated quartile (by people)",
    ]
    _QPOP_SHORT = {
        "Most populated quartile (by people)":     "Most Populated (Q1)",
        "2nd most populated quartile (by people)": "2nd Most Populated (Q2)",
        "3rd most populated quartile (by people)": "3rd Most Populated (Q3)",
        "4th most populated quartile (by people)": "Least Populated (Q4)",
    }

    df = long_df_hash.copy()
    df["fips"] = df["countyid"].astype(float).astype(int).astype(str).str.zfill(5)
    df[metric_col] = pd.to_numeric(df[metric_col], errors="coerce").clip(lower=0)
    df = df[~df["fips"].str[:2].isin(_EXCLUDE)].copy()

    is_pct = metric_col.startswith("pct_")
    def fmt_val(v):
        try:
            return f"{float(v):.1f}%" if is_pct else f"{float(v):,.0f}"
        except Exception:
            return "N/A"

    col_label = next(k for k, (c, *_) in _TRADE_METRICS.items() if c == metric_col)
    df["hover"] = (
        "<b>" + df["county_name"].fillna("") + "</b><br>"
        + "Population Quartile: " + df["qpop"].map(_QPOP_SHORT).fillna("") + "<br>"
        + col_label + ": " + df[metric_col].apply(fmt_val)
    )

    counties_geojson = load_counties_geojson()
    all_groups = ["All"] + _QPOP_ORDER
    traces = []

    zmin = 0
    zmax = df[metric_col].max()

    for group in all_groups:
        subset = df if group == "All" else df[df["qpop"] == group]
        sub = subset.dropna(subset=[metric_col])
        traces.append(go.Choropleth(
            geojson=counties_geojson,
            locations=sub["fips"],
            z=sub[metric_col],
            zmin=zmin, zmax=zmax,
            colorscale=colorscale,
            colorbar=dict(
                title=dict(text=col_label, font=dict(size=11, family="Roboto, sans-serif")),
                tickfont=dict(size=10, family="Roboto, sans-serif"),
                tickformat=".1f" if is_pct else ",.0f",
                len=0.6,
            ),
            marker_line_width=0.15,
            marker_line_color="white",
            hovertext=sub["hover"],
            hoverinfo="text",
            visible=(group == "All"),
        ))

    buttons = [dict(
        label="All Population Quartiles" if g == "All" else _QPOP_SHORT[g],
        method="update",
        args=[{"visible": [grp == g for grp in all_groups]}],
    ) for g in all_groups]

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text=f"<b>{col_label}</b>",
            x=0.5, xanchor="center",
            font=dict(size=16, color="black", family="Roboto, sans-serif"),
        ),
        geo=_GEO_CONUS,
        paper_bgcolor="white",
        showlegend=False,
        updatemenus=[dict(
            type="dropdown", direction="down",
            x=0.01, y=0.98, xanchor="left", yanchor="top",
            showactive=True, buttons=buttons,
            bgcolor="white", bordercolor="black",
            font={"size": 12, "color": "black"},
        )],
        margin=dict(l=0, r=0, t=60, b=0),
        height=580,
    )
    # Black colorbar text
    for trace in fig.data:
        if hasattr(trace, "colorbar"):
            trace.colorbar.title.font.color = "black"
            trace.colorbar.tickfont.color = "black"
    return fig

st.sidebar.write('### Select County')
state = st.sidebar.selectbox("State", sorted_states, index=default_index_st)
national_df = national_df[national_df["state"] == state]

sorted_counties = np.sort(national_df['county_name'].unique())
try:
    default_index_co = int(np.where(sorted_counties == default_county)[0][0])
except IndexError:
    default_index_co = 0

county = st.sidebar.selectbox("County", sorted_counties, index=default_index_co)

county_df = national_df[national_df["county_name"]==county]
county_long_df = long_df[long_df["county_name"]==county]
county_id = county_df["countyid"].iloc[0]

st.title("American Dream Achievability Progress Tracker")
st.markdown('<p style="font-size:18px;">See the local geography of global opportunity. For local policymakers, employers, and citizens.</p>', unsafe_allow_html=True)

def _hide_ak_hi(fig):
    """Cover the Alaska and Hawaii insets with white rectangles."""
    fig.update_layout(shapes=list(fig.layout.shapes or []) + [
        dict(type="rect", xref="paper", yref="paper",
             x0=0.0, y0=0.0, x1=0.30, y1=0.26,
             fillcolor="white", line_width=0, layer="above"),
        dict(type="rect", xref="paper", yref="paper",
             x0=0.30, y0=0.0, x1=0.44, y1=0.14,
             fillcolor="white", line_width=0, layer="above"),
    ])
    return fig

_national_fig = _hide_ak_hi(build_national_map(wide_df))
_tradserv_fig = _hide_ak_hi(build_trade_map(wide_df, "tradserv_exp_emp_2017_2022", "Blues"))

# Zoom setup
_centroids = get_county_centroids()
_county_fips = f"{int(county_id):05d}"
_zoom_geo = None
if _county_fips in _centroids:
    _clat, _clon = _centroids[_county_fips]
    _zoom_geo = dict(
        projection_type="mercator",
        center=dict(lat=_clat, lon=_clon),
        projection_scale=6,
        showland=True, landcolor="white",
        showcoastlines=False,
        showsubunits=True, subunitcolor="#444", subunitwidth=1.8,
        showlakes=False, showframe=False, bgcolor="white",
    )

def _apply_zoom(fig):
    if _zoom_geo:
        fig.update_geos(**_zoom_geo)
    return fig

_apply_zoom(_national_fig)
_apply_zoom(_tradserv_fig)

st.subheader("Manufacturing Trade Shocks")
st.caption("Estimated job flows from changes in manufacturing import competition and export growth. Use the dropdown to filter by population quartile.")
_trade_label = st.selectbox("Select metric", list(_TRADE_METRICS.keys()), key="trade_map_metric")
_trade_col, _trade_cs, _ = _TRADE_METRICS[_trade_label]
_trade_fig = _apply_zoom(_hide_ak_hi(build_trade_map(wide_df, _trade_col, _trade_cs)))
st.plotly_chart(_trade_fig, use_container_width=True, key="trade_map")

st.subheader("American Dream Potential Quintile by County")
st.caption("Calculated by workforce investment and exposure to global trade. Compared to counties with similar population.")

# Rankings within population quintile
_county_row  = wide_df[wide_df["countyid"] == county_id]
_county_qpop5 = _county_row["qpop5"].iloc[0] if len(_county_row) > 0 else None

def _q5_rank(col, higher_is_better=True):
    if col not in wide_df.columns or _county_qpop5 is None:
        return None, None
    bucket = wide_df[wide_df["qpop5"] == _county_qpop5][["countyid", col]].dropna(subset=[col])
    n = len(bucket)
    if n == 0:
        return None, None
    val_s = bucket[bucket["countyid"] == county_id][col]
    if len(val_s) == 0:
        return None, None
    val = val_s.iloc[0]
    rank = int((bucket[col] > val if higher_is_better else bucket[col] < val).sum()) + 1
    return rank, n

_rankings = [
    ("Potential",                     *_q5_rank("potential")),
    ("Manufacturing Share",           *_q5_rank("mfgsh")),
    ("Per-Pupil Spending",            *_q5_rank("ppupil_deflate_2022")),
    ("Tradable Services Growth %",    *_q5_rank("tradserv_exp_pct_emp")),
    ("Job Gain (Exports & Inputs) %", *_q5_rank("pct_pred_emp_gain")),
    ("Non-College in Mid/Upper Income Jobs",*_q5_rank("pct_star_midupp_2022")),
]
_valid = [(label, r, n) for label, r, n in _rankings if r is not None]

if _valid and _county_qpop5 is not None:
    _cells = "".join(
        f"<div style='display:inline-block;margin:4px 10px;text-align:center;'>"
        f"<div style='font-size:11px;color:#555;text-transform:uppercase;letter-spacing:0.4px;'>{label}</div>"
        f"<div style='font-size:17px;font-weight:600;color:#1a1a1a;'>{r}/{n}</div>"
        f"</div>"
        for label, r, n in _valid
    )
    st.markdown(
        f"<div style='background:#f7f7f8;border-radius:6px;padding:10px 16px;"
        f"margin-bottom:12px;font-family:Roboto,sans-serif;'>"
        f"<div style='font-size:12px;font-weight:600;color:#333;margin-bottom:4px;'>"
        f"{county} — Rankings within Population Quintile: {_county_qpop5} (1 = best)</div>"
        f"{_cells}</div>",
        unsafe_allow_html=True,
    )

st.subheader("American Dream Potential")
st.plotly_chart(_national_fig, use_container_width=True, key="national_map")

st.subheader("Tradable Services")
st.caption("Estimated jobs gained from tradable service exports. Use the dropdown on the map to filter by population quartile.")
st.plotly_chart(_tradserv_fig, use_container_width=True, key="tradserv_map")


st.divider()

county_cbp_df = cbp_df[(cbp_df["countyid"] == county_id)& (cbp_df['emp']> 1.)]
_tradserv_row = tradserv_df[tradserv_df["countyid"] == county_id]
tradserv_emp = _tradserv_row["emp"].iloc[0] if len(_tradserv_row) > 0 else 0
total_emp_2016 = cbp_df[cbp_df["countyid"] == county_id]["emp"].sum()
tradserv_pct = round(100 * tradserv_emp / total_emp_2016, 1) if total_emp_2016 > 0 else 0

_cbp_all = cbp_df[cbp_df["countyid"] == county_id]
mfg_emp_2016 = round(_cbp_all[(_cbp_all["sic87dd"] >= 2000) & (_cbp_all["sic87dd"] <= 3999)]["emp"].sum(), 0)
mfg_pct_2016 = round(100 * mfg_emp_2016 / total_emp_2016, 1) if total_emp_2016 > 0 else 0

total_jobs_2022      = round(county_df["employed_workers_2022"].iloc[0], 0) if len(county_df) > 0 else 0
college_jobs_2022    = round(county_df["employed_college2022"].iloc[0],  0) if len(county_df) > 0 else 0
noncollege_jobs_2022 = round(county_df["employed_STARs_2022"].iloc[0],   0) if len(county_df) > 0 else 0

_grad_row = grad_df[grad_df["county_fips"] == int(county_id)]
if len(_grad_row) > 0:
    pub_fouryear_grads_2022  = round(_grad_row["pub_fouryear_grads_2022"].iloc[0],  0)
    pub_subba_grads_2022     = round(_grad_row["pub_subba_grads_2022"].iloc[0],     0)
    priv_fouryear_grads_2022 = round(_grad_row["priv_fouryear_grads_2022"].iloc[0], 0)
    priv_subba_grads_2022    = round(_grad_row["priv_subba_grads_2022"].iloc[0],    0)
else:
    pub_fouryear_grads_2022 = pub_subba_grads_2022 = priv_fouryear_grads_2022 = priv_subba_grads_2022 = 0

# -----------------------------
# Compute stats
# -----------------------------
def simple_stats(co_df):

    star_wage    = round(co_df["star_median2022"].iloc[0],    0)
    college_wage = round(co_df["college_median2022"].iloc[0], 0)

    star_emp    = round(co_df["star_emp_rate_2022"].iloc[0],  2)
    college_emp = round(co_df["emp_rate_college2022"].iloc[0], 2)

    pct_educ2022    = round(100 * co_df["educ_pct_total_stloc2022"].iloc[0], 2)
    ppupil_educ2022 = round(co_df["ppupil_deflate_2022"].iloc[0], 2)

    job_loss     = round(co_df["pred_emp_loss"].iloc[0], 0)
    job_gain     = round(co_df["pred_emp_gain"].iloc[0], 0)
    pct_job_loss = round(co_df["pct_pred_emp_loss"].iloc[0] , 1)
    pct_job_gain = round(co_df["pct_pred_emp_gain"].iloc[0] , 1)

    mfgemp_loss = max(
        0,
        round(co_df["mfgemp2000"].iloc[0] - co_df["mfgemp2011"].iloc[0], 0)
    )

    serv_exp_job     = round(co_df["tradserv_exp_emp_2017_2022"].iloc[0], 0)
    pct_serv_exp_job = round(co_df["tradserv_exp_pct_2016emp"].iloc[0], 2) if "tradserv_exp_pct_2016emp" in co_df.columns else None

    return (
        star_wage, college_wage, star_emp, college_emp,
        pct_educ2022, ppupil_educ2022,
        job_loss, job_gain, pct_job_loss, pct_job_gain, mfgemp_loss, serv_exp_job, pct_serv_exp_job
    )

stats = simple_stats(county_df)

(
    star_wage, all_wage, star_emp, college_emp,
    pct_educ2022, ppupil_educ2022,
    job_loss, job_gain, pct_job_loss, pct_job_gain, mfgemp_loss, serv_exp_job, pct_serv_exp_job
) = stats



# -----------------------------
# Dashboard
# -----------------------------
st.subheader(f"{county} County Overview")
st.caption("Wage data in in $2026. Non-college workers includes workers with a high school diploma but no four-year college degree.")

_COLORS = {
    "red":     ("#FDF2F2", "#B85C5C"),
    "green":   ("#F2F7F3", "#4A8A57"),
    "purple":  ("#F3F2FA", "#6B62C0"),
    "orange":  ("#FDF6EE", "#C07A38"),
    "neutral": ("#F7F7F8", "#888888"),
}

def cmetric(label, value, style="neutral"):
    bg, accent = _COLORS[style]
    st.markdown(
        f'<div style="background:{bg};border-left:3px solid {accent};'
        f'padding:10px 14px;border-radius:4px;margin-bottom:5px;">'
        f'<div style="font-size:11px;color:#666;letter-spacing:0.4px;text-transform:uppercase;margin-bottom:3px;">{label}</div>'
        f'<div style="font-size:20px;font-weight:600;color:#1a1a1a;letter-spacing:-0.3px;">{value}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# metrics
_tab_general, _tab_compare = st.tabs(["General", "Comparisons"])

with _tab_general:
    st.metric("Total Employed Workers (2022)", f"{total_jobs_2022:,.0f}")

    col1, col2 = st.columns(2)

    # Row 1: Non-college | College
    with col1: cmetric("Non-College Educated Employed Workers (2022)", f"{noncollege_jobs_2022:,.0f}", "purple")
    with col2: cmetric("College Educated Employed Workers (2022)", f"{college_jobs_2022:,.0f}", "orange")

    # Row 2: Wages
    with col1: cmetric("Non-College Median Wage (2022)", f"${star_wage:,.0f}", "purple")
    with col2: cmetric("College Median Wage (2022)", f"${all_wage:,.0f}", "orange")

    # Row 3: Employment rates
    with col1: cmetric("Non-College Employment Rate (2022)", f"{star_emp}%", "purple")
    with col2: cmetric("College Employment Rate (2022)", f"{college_emp}%", "orange")

    # Row 4: Tradable services
    with col1: cmetric("Tradable Services Employment (2016)", f"{tradserv_emp:,.0f}")
    with col2: cmetric("Tradable Services Share of Employment (2016)", f"{tradserv_pct}%")

    # Row 5: Manufacturing (2016)
    with col1: cmetric("Manufacturing Employment (2016)", f"{mfg_emp_2016:,.0f}")
    with col2: cmetric("Manufacturing Share of Employment (2016)", f"{mfg_pct_2016}%")

    # Row 6: Education spending
    with col1: cmetric("Education Spending (% local budget)", f"{pct_educ2022}%")
    with col2: cmetric("Per-Pupil Spending", f"${ppupil_educ2022:,.0f}")

    # Row 7: Mfg jobs lost
    with col1: cmetric("Manufacturing Jobs Lost (1991–2011)", f"{mfgemp_loss:,.0f}", "red")

    # Row 8: Total estimated job flows
    with col1: cmetric("Est. Job Loss from Low-Wage Manuf. Imports (1991–2011)", f"{job_loss:,.0f}", "red")
    with col2: cmetric("Est. Job Gain from Manuf. Exports & Inputs (2011–2022)", f"{job_gain:,.0f}", "green")

    # Row 9: Tradable services job growth (2017–2022)
    with col1: cmetric("Tradable Services Job Growth (2017–2022)", f"{serv_exp_job:,.0f}", "green")

    # Row 11: Public graduates by level (2022)
    with col1: cmetric("Public 4-Year Graduates (2022)", f"{pub_fouryear_grads_2022:,.0f}")
    with col2: cmetric("Public Sub-Bachelor's Graduates (2022)", f"{pub_subba_grads_2022:,.0f}")

    # Row 12: Private graduates by level (2022)
    with col2: cmetric("Private 4-Year Graduates (2022)", f"{priv_fouryear_grads_2022:,.0f}")
    with col2: cmetric("Private Sub-Bachelor's Graduates (2022)", f"{priv_subba_grads_2022:,.0f}")

with _tab_compare:
    st.caption(f"How {county} compares to counties in the same population quintile (Quintile {_county_qpop5}). Rank 1 = best.")

    # Define comparison metrics: (display label, wide_df col, higher_is_better, format_fn)
    _cmp_metrics = [
        ("Non-College Median Wage",                        "star_median2022",             True,  lambda v: f"${v:,.0f}"),
        ("Non-College Employment Rate",                    "star_emp_rate_2022",          True,  lambda v: f"{v:.1f}%"),
        ("Non-College in Mid/Upper Income Jobs",           "pct_star_midupp_2022",        True,  lambda v: f"{v:.1f}%"),
        ("Tradable Services Share (2016)",                 "tradserv_pct_2016",           True,  lambda v: f"{v:.1f}%"),
        ("Manufacturing Share (2016)",                     "mfgsh",                       True,  lambda v: f"{v:.2f}"),
        ("Per-Pupil Spending",                             "ppupil_deflate_2022",         True,  lambda v: f"${v:,.0f}"),
        ("Education Spending % of Local Budget",           "educ_pct_total_stloc2022",    True,  lambda v: f"{v:.1%}"),
        ("Job Gain from Exports & Inputs, % All",          "pct_pred_emp_gain",           True,  lambda v: f"{v:.1f}%"),
        ("Tradable Services Export Job Growth, % All (2017-2022)", "tradserv_exp_pct_2016emp", True, lambda v: f"{v:.1f}%"),
        ("Sub-Bachelor's Grads per Capita",                "subba_grads_per_wap_2022",    True,  lambda v: f"{v:.3f}"),
    ]

    _under, _over = [], []
    for _lbl, _col, _hib, _fmt in _cmp_metrics:
        _rank, _n = _q5_rank(_col, higher_is_better=_hib)
        if _rank is None or _n is None:
            continue
        _row = wide_df[wide_df["countyid"] == county_id]
        _val = _row[_col].iloc[0] if len(_row) > 0 and _col in _row.columns else None
        _val_str = _fmt(_val) if _val is not None and not (isinstance(_val, float) and __import__('math').isnan(_val)) else "N/A"
        _entry = (_lbl, _rank, _n, _val_str)
        # underperforming: rank in bottom half (rank > n/2)
        if _rank > _n / 2:
            _under.append(_entry)
        else:
            _over.append(_entry)

    _under.sort(key=lambda x: x[1], reverse=True)  # worst first
    _over.sort(key=lambda x: x[1])                  # best first

    _cc1, _cc2 = st.columns(2)
    with _cc1:
        st.markdown("#### 🔴 Underperforming")
        for _lbl, _rank, _n, _val_str in _under:
            st.markdown(
                f'<div style="background:#FDF2F2;border-left:3px solid #B85C5C;'
                f'padding:8px 12px;border-radius:4px;margin-bottom:5px;">'
                f'<div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:0.4px;">{_lbl}</div>'
                f'<div style="font-size:18px;font-weight:600;color:#1a1a1a;">{_val_str}</div>'
                f'<div style="font-size:11px;color:#B85C5C;">Rank {_rank}/{_n} in quintile</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    with _cc2:
        st.markdown("#### 🟢 Overperforming")
        for _lbl, _rank, _n, _val_str in _over:
            st.markdown(
                f'<div style="background:#F2F7F3;border-left:3px solid #4A8A57;'
                f'padding:8px 12px;border-radius:4px;margin-bottom:5px;">'
                f'<div style="font-size:11px;color:#666;text-transform:uppercase;letter-spacing:0.4px;">{_lbl}</div>'
                f'<div style="font-size:18px;font-weight:600;color:#1a1a1a;">{_val_str}</div>'
                f'<div style="font-size:11px;color:#4A8A57;">Rank {_rank}/{_n} in quintile</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.divider()
    st.markdown("**Coming soon:**")
    st.markdown(
        "- State & local investment in community & technical colleges\n"
        "- K–12 STEM courses\n"
        "- Infrastructure access\n"
        "- Apprenticeships"
    )

st.subheader("Wages & Employment")
st.caption("Values normalized to percentile rank within each population size group. Darker blue = higher relative value. Use the dropdown to filter by population quartile.")
_wage_label = st.selectbox("Select metric", list(_WAGE_METRICS.keys()), key="wage_map_metric")
_wage_col, _ = _WAGE_METRICS[_wage_label]
_wage_fig = _apply_zoom(_hide_ak_hi(build_wage_map(long_df, _wage_col)))
st.plotly_chart(_wage_fig, use_container_width=True, key="wage_map")

### INDUSTRY TABLE
county_cbp_df["l_m_dw_uswld_2023"] = county_cbp_df["l_m_dw_uswld_2023"].round(1)
st.subheader("Industries by Employment")
_table_cols = ["sic87dd_desc", "emp","l_m_dw_uswld_2023"]
industry_table = (
    county_cbp_df[_table_cols]
    .sort_values("emp", ascending=False)
    .rename(columns={
        "sic87dd_desc": "Industry",
        "emp": "Employment",
        "l_m_dw_uswld_2023": "Est. Imported Inputs Benefit (0-25)"
    })
    .reset_index(drop=True)
)
industry_table["Employment"] = industry_table["Employment"].apply(lambda x: f"{x:,.0f}")

# Faux columns seeded by county for consistency
_rng = np.random.default_rng(int(county_id) + 42)
n = len(industry_table)
industry_table["Non-College Workers ⚠"] = [f"{int(v):,}" for v in
    county_cbp_df.sort_values("emp", ascending=False)["emp"].values * _rng.uniform(0.52, 0.82, n)]
growth = _rng.uniform(-9, 18, n)
industry_table["Job Growth (%) ⚠"] = [f"{v:+.1f}%" for v in growth]
unfilled = (
    county_cbp_df.sort_values("emp", ascending=False)["emp"].values
    * _rng.uniform(0.03, 0.13, n)
).astype(int)
industry_table["Unfilled Positions ⚠"] = [f"{v:,}" for v in unfilled]
wages = _rng.integers(28000, 92000, n)
industry_table["Median Wage ⚠"] = [f"${v:,}" for v in wages]

st.dataframe(industry_table, width="stretch", hide_index=True)
st.caption("Using 2016 Employment, 2023 Imports, and 1992 Input-Output Table. ⚠ Columns marked ⚠ show illustrative placeholder data.")

### OPPORTUNITY OCCUPATION TABLE
st.subheader("Non-College Educated Opportunity Occupations")

_OCC_DATA = [
    ("Registered Nurse",         "Healthcare",  77_400, 6,   15, 12),
    ("Heavy Truck Driver",        "Transportation / Warehousing", 48_300, 4,  85, 68),
    ("Electrician",               "Construction / Manufacturing", 57_200, 11, 84, 41),
    ("Software Developer",        "Professional Services / Finance", 121_000, 25, 9, 74),
    ("Welder",                    "Manufacturing", 44_100, 3,  91, 79),
    ("Construction Laborer",      "Construction", 38_600, 5,  90, 22),
    ("Machinist",                 "Manufacturing", 47_300, 7,  86, 81),
    ("Medical Assistant",         "Healthcare",  36_200, 16, 58, 8),
    ("HVAC Technician",           "Construction / Building Services", 52_700, 9, 83, 30),
    ("Logistics Coordinator",     "Wholesale Trade / Transportation", 50_100, 8, 72, 61),
    ("Customer Service Rep",      "Retail / Finance / Healthcare", 35_800, -4, 69, 35),
    ("Industrial Engineer",       "Manufacturing / Consulting", 92_000, 10, 18, 77),
]

_occ_rng = np.random.default_rng(int(county_id) + 99)
occ_rows = []
for occ, industries, wage, growth_pct, noncoll_pct, global_pct in _OCC_DATA:
    jobs_now = int(_occ_rng.integers(200, 4000))
    occ_rows.append({
        "Occupation":                     occ,
        "Jobs (County Est.) ⚠":           f"{jobs_now:,}",
        "Projected Growth (%) ⚠":         f"{growth_pct:+d}%",
        "Common Industries":              industries,
        "Median Wage ⚠":                  f"${wage:,}",
        "% Non-College Workers ⚠":        f"{noncoll_pct}%",
        "% in Globally Exposed Inds. ⚠":  f"{global_pct}%",
    })

occ_df = pd.DataFrame(occ_rows)
st.dataframe(occ_df, width="stretch", hide_index=True)
st.caption("⚠ Columns marked ⚠ show illustrative placeholder data.")

### DIVISION PIE CHART
def sic_division(code):
    if   100  <= code <= 999:  return "Agriculture, Forestry & Fishing"
    elif 1000 <= code <= 1499: return "Mining"
    elif 1500 <= code <= 1799: return "Construction"
    elif 2000 <= code <= 3999: return "Manufacturing"
    elif 4000 <= code <= 4999: return "Transportation, Communications & Utilities"
    elif 5000 <= code <= 5199: return "Wholesale Trade"
    elif 5200 <= code <= 5999: return "Retail Trade"
    elif 6000 <= code <= 6799: return "Finance, Insurance & Real Estate"
    elif 7000 <= code <= 8999: return "Services"
    elif 9100 <= code <= 9729: return "Public Administration"
    else:                      return "Other"

div_df = county_cbp_df.copy()
div_df["division"] = div_df["sic87dd"].apply(sic_division)
div_agg = div_df.groupby("division")["emp"].sum().reset_index()
div_agg = div_agg[div_agg["emp"] > 0].sort_values("emp", ascending=False)


fig_pie = go.Figure(go.Pie(
    labels=div_agg["division"],
    values=div_agg["emp"],
    hole=0.3,
    textinfo="percent",
    textfont=dict(size=13, color="white", family="Roboto, sans-serif"),
    insidetextorientation="radial",
))
fig_pie.update_layout(
    title=dict(
        text="Employment by Industry Division (2016)",
        x=0.5, xanchor="center",
        font=dict(size=18, color="black", family="Roboto, sans-serif")
    ),
    showlegend=True,
    legend=dict(
        font=dict(size=13, color="black", family="Roboto, sans-serif"),
        bgcolor="white",
        bordercolor="black",
        borderwidth=1,
        x=1.02,
        xanchor="left",
        y=0.5,
        yanchor="middle",
    ),
    paper_bgcolor="#F4F4F4",
    margin=dict(t=60, b=20, l=20, r=220),
)
st.plotly_chart(fig_pie, width="stretch", key="pie_chart")


### GRAPHS
def employment_trends(county_df):

    years = county_df["year"]
    county_emp = county_df["star_emp_rate"]
    peer_emp = county_df["star_emp_rate_qpop_avg"]
    name = county_df['name_short'].iloc[0]

    fig3 = make_subplots(specs=[[{"secondary_y": False}]])

    fig3.update_layout(
        width=900,
        title={
            'text': f"Change in Non-College Employment Rate in <br> {name} vs Similar-Sized Counties",
            'x': 0.5,
            'y': 0.94,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=21, color="black", family="Roboto, sans-serif"),
        },

        xaxis=dict(
            title=dict(text='Year', font=dict(color='black', size=20, family="Roboto Medium, sans-serif")),
            range=[1990, 2023],
            dtick=5,
            title_standoff=30,
            ticklabelposition="outside right",
            tickfont=dict(color='black', size=20, family="Roboto, sans-serif"),
        ),

        yaxis=dict(
            title=dict(text='Non-College<br>Employment Rate (%)', font=dict(color='black', size=20, family="Roboto Medium, sans-serif")),
            dtick = 2,
            range=[min(min(county_emp),min(peer_emp))-2,max(max(county_emp),max(peer_emp))+2],
            title_standoff=25,
            tickfont=dict(color='black', size=18, family="Roboto, sans-serif"),
        ),

        margin=dict(t=105, r=0, l=155, b=100),

        legend=dict(
            font=dict(size=14, color="black"),
            x=.35,
            xanchor='right',
            y=.35,
            yanchor='top',
            bgcolor='#ECECEC',
            bordercolor='black',
            borderwidth=1
        ),

        paper_bgcolor='#F4F4F4',
        plot_bgcolor='#F4F4F4',
    )
    # Import Shock shaded region
    fig3.add_shape(
        x0=2000.,
        x1=2011.,
        y0=math.ceil(min(min(county_emp),min(peer_emp))-2),
        y1=max(max(county_emp),max(peer_emp))+2,
        fillcolor="gray",
        opacity=0.15,
        line_width=0,
        layer="below",
    )
    
    fig3.add_annotation(
        x=2005.5,
        y=0.04,
        xref="x",
        yref="paper",
        text="Import Shock",
        showarrow=False,
        font=dict(size=14, color='black')
    )

    # County line
    fig3.add_trace(
        go.Scatter(
            x=years,
            y=county_emp,
            mode='lines',
            line=dict(color='#F7A072', width=3),
            name=name
        )
    )

    # Peer counties line
    fig3.add_trace(
        go.Scatter(
            x=years,
            y=peer_emp,
            mode='lines',
            line=dict(color='#445E93', width=3),
            name='Similar Counties'
        )
    )

    st.plotly_chart(fig3,  width='stretch', key="fig3_chart")

employment_trends(county_long_df)

def county_dual_axis_chart(df):
    df = df.copy()
    name = df['name_short'].iloc[0]

    fig = make_subplots(specs=[[{"secondary_y": False}]])

    fig.update_layout(
        width=900,
        title={'text': f"Change in Manufacturing Jobs, and Good-Paying Jobs, <br> for Non-College Workers in {name}",
               'x':0.5,
               'y':0.94,
               'xanchor':'center',
               'font': dict(size=21, color="black", family="Roboto, sans-serif")},


        xaxis=dict(
            title=dict(text="Year", font=dict(color='black', size=20, family="Roboto Medium, sans-serif")),
            range=[1990,2022],
            dtick=5,
            tickfont=dict(color='black', size=20, family="Roboto, sans-serif"),
        ),

        yaxis=dict(
            title=dict(text="Percent of Total (%)", font=dict(color='black', size=18, family="Roboto Medium, sans-serif")),
            range=[0,100],
            tickfont=dict(color='black', size=18, family="Roboto, sans-serif"),
        ),

        paper_bgcolor='#F4F4F4',
        plot_bgcolor='#F4F4F4',

        legend=dict(
            font=dict(size=14, color="black"),
            bgcolor='#ECECEC',
            bordercolor='black',
            x=.99,
            xanchor='right',
            y=.35,
            yanchor='top',
            borderwidth=1,
        )
    )

    # Import Shock shading
    fig.add_shape(
        x0=2000,
        x1=2011,
        y0=0,
        y1=100,
        fillcolor="gray",
        opacity=0.15,
        line_width=0
    )
    fig.add_annotation(
        x=2005.5,
        y=0.02,
        xref="x",
        yref="paper",
        text="Import Shock",
        showarrow=False,
        font=dict(size=14, color='black')
    )


    # scale mfgsh by 100
    df['mfgsh'] = df['mfgsh']*100

    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["mfgsh"],
            line=dict(color="#F7A072", width=3),
            mode="lines",
            name="Manufacturing Share"
        ),
        secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["pct_star_midupp"],
            line=dict(color="#445E93", width=3),
            mode="lines",
            name="Non-College Mid/Upper Income Jobs"
        ),
        secondary_y=False
    )

    st.plotly_chart(fig, width='stretch', key="fig_chart")

county_dual_axis_chart(county_long_df)


