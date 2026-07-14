"""Geographic constants and Plotly map builders for the main dashboard."""

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .paths import COUNTIES_GEOJSON


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
@st.cache_resource
def load_counties_geojson():
    """Load the shared county geometry from the repository, without network I/O."""
    with COUNTIES_GEOJSON.open(encoding="utf-8") as geojson_file:
        return json.load(geojson_file)

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

WAGE_METRICS = {
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

    col_label, prefix = next((k, p) for k, (c, p) in WAGE_METRICS.items() if c == metric_col)
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

TRADE_METRICS = {
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

    col_label = next(k for k, (c, *_) in TRADE_METRICS.items() if c == metric_col)
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

def hide_ak_hi(fig):
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


def county_zoom_settings(county_id):
    centroids = get_county_centroids()
    county_fips = f"{int(county_id):05d}"
    if county_fips not in centroids:
        return None
    latitude, longitude = centroids[county_fips]
    return dict(
        projection_type="mercator",
        center=dict(lat=latitude, lon=longitude),
        projection_scale=6,
        showland=True,
        landcolor="white",
        showcoastlines=False,
        showsubunits=True,
        subunitcolor="#444",
        subunitwidth=1.8,
        showlakes=False,
        showframe=False,
        bgcolor="white",
    )


def apply_zoom(fig, zoom_geo):
    if zoom_geo:
        fig.update_geos(**zoom_geo)
    return fig
