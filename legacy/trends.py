"""
County & National Trends Analysis
Visualize economic trends across counties over time using:
  1. Bubble Charts: Wage vs Employment across all counties
  2. Line Graphs: National aggregates and county percentiles
  3. Comparative Analysis: County performance relative to state/national averages
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from urllib.request import urlopen
import streamlit.components.v1 as components
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

st.set_page_config(page_title="Trends Analysis", page_icon="📈", layout="wide")

# Custom font styling
streamlit_style = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@100;400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    </style>
"""
st.markdown(streamlit_style, unsafe_allow_html=True)

# Load and cache datasets
@st.cache_data
def load_data():
    national_df = pd.read_stata("county_all_vars_index.dta")
    long_df = pd.read_csv("county_all_vars_post_index.csv")
    return national_df, long_df

@st.cache_data
def load_grad_data():
    df = pd.read_stata("county_panel_90001122.dta")
    df2022 = df[df["year"] == 2022].copy()
    df2022["county_fips"] = df2022["county_fips"].astype("Int64")
    grads = df2022.groupby("county_fips").apply(
        lambda g: pd.Series({
            "total_fouryear_grads_2022": g.loc[g["level"] == "4+ years", "numbergraduates"].sum(),
            "total_subba_grads_2022":    g.loc[g["level"] != "4+ years", "numbergraduates"].sum(),
        })
    ).reset_index()
    return grads

national_df, long_df = load_data()
grad_df = load_grad_data()

# Remove CT planning regions
_ct_mask = national_df["county_name"].str.contains("Planning Region", case=False, na=False)
national_df = national_df[~_ct_mask].copy()

# Merge grad totals and normalise by working-age population
_grad_map_cols = grad_df[["county_fips", "total_fouryear_grads_2022", "total_subba_grads_2022"]].copy()
_grad_map_cols["county_fips"] = _grad_map_cols["county_fips"].astype(float)
national_df = national_df.merge(_grad_map_cols, left_on="countyid", right_on="county_fips", how="left").drop(columns="county_fips")
national_df["total_fouryear_grads_2022"] = national_df["total_fouryear_grads_2022"].fillna(0)
national_df["total_subba_grads_2022"]    = national_df["total_subba_grads_2022"].fillna(0)
national_df["fouryear_grads_per_wap_2022"] = national_df["total_fouryear_grads_2022"] / national_df["workagepop2022"].replace(0, float("nan"))
national_df["subba_grads_per_wap_2022"]    = national_df["total_subba_grads_2022"]    / national_df["workagepop2022"].replace(0, float("nan"))

# Assign China shock quartiles (fixed per county, normalized by county size)
_county_shock = long_df.groupby("countyid").agg(
    _pred_emp_loss=("pred_emp_loss", "mean"),
    _totemp=("totemp", "mean"),
).reset_index()
_county_shock["_shock_per_worker"] = _county_shock["_pred_emp_loss"] / _county_shock["_totemp"]
_county_shock["china_shock_q"] = pd.qcut(
    _county_shock["_shock_per_worker"], q=4,
    labels=["Q1 (Lowest)", "Q2", "Q3", "Q4 (Highest)"],
    duplicates="drop",
)
long_df = long_df.merge(_county_shock[["countyid", "china_shock_q"]], on="countyid", how="left")

# Page header
st.title("County & National Trends Analysis")
st.caption("Explore county economic trajectories and national patterns · 1990–2023")

# ── National County Map ───────────────────────────────────────────────────────
@st.cache_data
def load_counties_geojson():
    with urlopen("https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json") as response:
        return json.load(response)

_NAT_MAP_METRICS = {
    "Non-College Median Wage (2022)":            ("star_median2022",           1,   "$,.0f"),
    "College Median Wage (2022)":                ("college_wage2022",           1,   "$,.0f"),
    "Non-College Employment Rate (2022)":        ("STAR_emp_rate2022",          1,   ",.1f"),
    "College Employment Rate (2022)":            ("emp_rate_college2022",       1,   ",.1f"),
    "Est. Job Loss from Low-Wage Imports":       ("pred_emp_loss",              1,   ",.0f"),
    "Est. Job Gain from Exports & Inputs":       ("pred_emp_gain",              1,   ",.0f"),
    "Education Spending (% Local Budget, 2022)": ("educ_pct_total_stloc2022", 100,   ",.1f"),
    "Per-Pupil Spending (2022)":                 ("spend_ppupil_2022",          1,   "$,.0f"),
    "Tradable Services Job Growth (2017–2022)":  ("tradserv_exp_emp_2017_2022", 1,   ",.0f"),
    "4-Year Graduates per Working-Age Pop. (2022)":         ("fouryear_grads_per_wap_2022", 1, ",.4f"),
    "Sub-Bachelor's Graduates per Working-Age Pop. (2022)": ("subba_grads_per_wap_2022",    1, ",.4f"),
}

_nat_label = st.selectbox("Select metric to map", list(_NAT_MAP_METRICS.keys()), key="nat_map_metric")
_nat_col, _nat_scale, _nat_fmt = _NAT_MAP_METRICS[_nat_label]

_nat_df = national_df[~national_df["state"].isin(["AK", "HI"])][
    ["countyid", "county_name", "state", _nat_col]
].dropna(subset=[_nat_col]).copy()
_nat_df["fips"] = _nat_df["countyid"].astype(int).apply(lambda x: f"{x:05d}")
_nat_df["_val"] = _nat_df[_nat_col] * _nat_scale

_nat_geo = load_counties_geojson()

fig_nat = go.Figure(go.Choropleth(
    geojson=_nat_geo,
    locations=_nat_df["fips"],
    z=_nat_df["_val"],
    colorscale="Blues",
    colorbar=dict(
        title=dict(text=_nat_label, font=dict(family="Roboto, sans-serif", size=12, color="black")),
        tickfont=dict(family="Roboto, sans-serif", size=11, color="black"),
        tickformat=_nat_fmt,
    ),
    text=_nat_df["county_name"] + ", " + _nat_df["state"],
    hovertemplate="<b>%{text}</b><br>" + _nat_label + ": %{z:" + _nat_fmt + "}<extra></extra>",
    marker_line_color="white",
    marker_line_width=0.3,
))
fig_nat.update_geos(scope="usa", visible=False)
fig_nat.update_layout(
    title=dict(
        text=_nat_label + " — All U.S. Counties",
        x=0.5, xanchor="center",
        font=dict(size=18, color="black", family="Roboto, sans-serif"),
    ),
    paper_bgcolor="#F4F4F4",
    margin=dict(t=60, b=10, l=10, r=10),
    height=540,
)
st.plotly_chart(fig_nat, width="stretch")

# ── Commuting Zone Map ────────────────────────────────────────────────────────
@st.cache_data
def load_czone_mapping():
    df = pd.read_csv("czone_county.csv", dtype={"county_fips": str})
    df["county_fips"] = df["county_fips"].str.zfill(5)
    return df

# Aggregation rule per metric: sum for employment levels, mean for rates/wages
_CZ_MAP_METRICS = {
    "Non-College Median Wage (2022)":            ("star_median2022",            1,   "$,.0f", "mean"),
    "College Median Wage (2022)":                ("college_wage2022",            1,   "$,.0f", "mean"),
    "Non-College Employment Rate (2022)":        ("STAR_emp_rate2022",           1,   ",.1f",  "mean"),
    "College Employment Rate (2022)":            ("emp_rate_college2022",        1,   ",.1f",  "mean"),
    "Est. Job Loss from Low-Wage Imports":       ("pred_emp_loss",               1,   ",.0f",  "sum"),
    "Est. Job Gain from Exports & Inputs":       ("pred_emp_gain",               1,   ",.0f",  "sum"),
    "Education Spending (% Local Budget, 2022)": ("educ_pct_total_stloc2022",  100,   ",.1f",  "mean"),
    "Per-Pupil Spending (2022)":                 ("spend_ppupil_2022",           1,   "$,.0f", "mean"),
    "Tradable Services Job Growth (2017–2022)":  ("tradserv_exp_emp_2017_2022",  1,   ",.0f",  "sum"),
    "4-Year Graduates per Working-Age Pop. (2022)":         ("fouryear_grads_per_wap_2022", 1, ",.4f", "mean"),
    "Sub-Bachelor's Graduates per Working-Age Pop. (2022)": ("subba_grads_per_wap_2022",    1, ",.4f", "mean"),
}

st.subheader("Commuting Zone Map")
_cz_label = st.selectbox("Select metric to map", list(_CZ_MAP_METRICS.keys()), key="cz_map_metric")
_cz_col, _cz_scale, _cz_fmt, _cz_agg = _CZ_MAP_METRICS[_cz_label]

_czone_xwalk = load_czone_mapping()

# Build county-level frame with FIPS, filtered to contiguous 48
_cz_base = national_df[~national_df["state"].isin(["AK", "HI"])][
    ["countyid", _cz_col]
].dropna(subset=[_cz_col]).copy()
_cz_base["fips"] = _cz_base["countyid"].astype(int).apply(lambda x: f"{x:05d}")

# Attach czone id and label to each county
_cz_base = _cz_base.merge(
    _czone_xwalk[["county_fips", "czone", "NameoflargestplaceinCommuti"]],
    left_on="fips", right_on="county_fips", how="left",
)

# Aggregate to CZ level
_cz_agg_df = (
    _cz_base.groupby("czone")
    .agg(_val=(_cz_col, _cz_agg), cz_name=("NameoflargestplaceinCommuti", "first"))
    .reset_index()
)
_cz_agg_df["_val"] = _cz_agg_df["_val"] * _cz_scale

# Join CZ value back to every county in that CZ
_cz_plot = _cz_base[["fips", "czone"]].merge(
    _cz_agg_df[["czone", "_val", "cz_name"]], on="czone", how="left"
)

fig_cz = go.Figure(go.Choropleth(
    geojson=_nat_geo,
    locations=_cz_plot["fips"],
    z=_cz_plot["_val"],
    colorscale="Oranges",
    colorbar=dict(
        title=dict(text=_cz_label, font=dict(family="Roboto, sans-serif", size=12, color="black")),
        tickfont=dict(family="Roboto, sans-serif", size=11, color="black"),
        tickformat=_cz_fmt,
    ),
    text=_cz_plot["cz_name"],
    hovertemplate="<b>%{text}</b><br>" + _cz_label + ": %{z:" + _cz_fmt + "}<extra></extra>",
    marker_line_color="white",
    marker_line_width=0.3,
))
fig_cz.update_geos(scope="usa", visible=False)
fig_cz.update_layout(
    title=dict(
        text=_cz_label + " — Commuting Zones",
        x=0.5, xanchor="center",
        font=dict(size=18, color="black", family="Roboto, sans-serif"),
    ),
    paper_bgcolor="#F4F4F4",
    margin=dict(t=60, b=10, l=10, r=10),
    height=540,
)
st.plotly_chart(fig_cz, width="stretch")
st.caption("Counties shaded by their commuting zone's aggregated value. Wages and rates are averaged across counties; employment counts are summed.")

# ── ArcGIS Map — County Boundaries + Overlays + Highway Network ──────────────
st.subheader("ArcGIS Map — County Boundaries, Economic Distress & Highway Network")

# Public service URLs
_COUNTY_SVC     = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Counties_Generalized/FeatureServer/0"
_INTERSTATE_SVC = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Freeway_System/FeatureServer/1"
_STATE_HWY_SVC  = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Freeway_System/FeatureServer/2"
# Community Economic Distress Index — public Feature Service (item 4ccbeee3fdbb4d7ca9e8d991d240a416)
_DCI_SVC        = "https://services8.arcgis.com/cOQY5d2zYaXw1BYI/arcgis/rest/services/Community_Economic_Distress_Index/FeatureServer/0"

@st.cache_resource
def _get_arcgis_layer_urls():
    """Connect anonymously and return validated FeatureLayer service URLs."""
    gis = GIS()
    return (
        FeatureLayer(_COUNTY_SVC,     gis=gis).url,
        FeatureLayer(_INTERSTATE_SVC, gis=gis).url,
        FeatureLayer(_STATE_HWY_SVC,  gis=gis).url,
        FeatureLayer(_DCI_SVC,        gis=gis).url,
    )

_county_url, _interstate_url, _state_hwy_url, _dci_url = _get_arcgis_layer_urls()

# Mfg employment decline (mfgsh2011 - mfgsh1991) × 100, keyed by 5-digit FIPS string
_mfg_cols = national_df[["countyid", "mfgsh1991", "mfgsh2011"]].dropna()
_mfg_decline_json = json.dumps({
    f"{int(r.countyid):05d}": round((r.mfgsh2011 - r.mfgsh1991) * 100, 2)
    for _, r in _mfg_cols.iterrows()
})

def _arcgis_map_html(county_url, interstate_url, state_hwy_url, dci_url, mfg_json):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="initial-scale=1, maximum-scale=1, user-scalable=no" />
      <link rel="stylesheet" href="https://js.arcgis.com/4.29/esri/themes/light/main.css" />
      <script src="https://js.arcgis.com/4.29/"></script>
      <style>
        html, body, #viewDiv {{ margin: 0; padding: 0; height: 640px; width: 100%; }}
      </style>
    </head>
    <body>
      <div id="viewDiv"></div>
      <script>
        require([
          "esri/Map",
          "esri/views/MapView",
          "esri/layers/FeatureLayer",
          "esri/layers/GeoJSONLayer",
          "esri/widgets/Legend",
          "esri/widgets/LayerList",
          "esri/widgets/ScaleBar"
        ], function(Map, MapView, FeatureLayer, GeoJSONLayer, Legend, LayerList, ScaleBar) {{

          // ── Mfg decline data (Python-computed, keyed by 5-digit FIPS) ──────
          var mfgData = {mfg_json};

          // ── Community Economic Distress Index (tract-level Feature Service) ─
          var dciLayer = new FeatureLayer({{
            url: "{dci_url}",
            title: "Community Economic Distress Index",
            opacity: 0.70,
            renderer: {{
              type: "class-breaks",
              field: "INDEX_PCTL",
              legendOptions: {{ title: "Distress Index Percentile" }},
              classBreakInfos: [
                {{ minValue: 0,  maxValue: 20,  label: "0–20 (Least Distressed)",  symbol: {{ type: "simple-fill", color: [255, 255, 178, 160], outline: {{ width: 0 }} }} }},
                {{ minValue: 20, maxValue: 40,  label: "20–40",                    symbol: {{ type: "simple-fill", color: [254, 204,  92, 160], outline: {{ width: 0 }} }} }},
                {{ minValue: 40, maxValue: 60,  label: "40–60",                    symbol: {{ type: "simple-fill", color: [253, 141,  60, 170], outline: {{ width: 0 }} }} }},
                {{ minValue: 60, maxValue: 80,  label: "60–80",                    symbol: {{ type: "simple-fill", color: [240,  59,  32, 180], outline: {{ width: 0 }} }} }},
                {{ minValue: 80, maxValue: 100, label: "80–100 (Most Distressed)", symbol: {{ type: "simple-fill", color: [189,   0,  38, 190], outline: {{ width: 0 }} }} }}
              ]
            }},
            popupTemplate: {{
              title: "{{County_Name}}, {{ST_ABBREV}}",
              content: [{{ type: "fields", fieldInfos: [
                {{ fieldName: "INDEX_",               label: "Distress Index Score"    }},
                {{ fieldName: "INDEX_PCTL",            label: "Distress Percentile"    }},
                {{ fieldName: "Percent_below_poverty", label: "% Below Poverty"        }},
                {{ fieldName: "Percent_unemployed",    label: "% Unemployed"           }},
                {{ fieldName: "Percent_less_than_HighSchool", label: "% < High School" }}
              ]}}]
            }}
          }});

          // ── County boundary outline layer ────────────────────────────────────
          var countyLayer = new FeatureLayer({{
            url: "{county_url}",
            title: "County Boundaries",
            renderer: {{
              type: "simple",
              symbol: {{ type: "simple-fill", color: [0,0,0,0], outline: {{ color: [70,70,70,200], width: 0.5 }} }}
            }},
            popupTemplate: {{ title: "{{NAME}}, {{STATE_NAME}}" }}
          }});

          // ── Interstate highways ───────────────────────────────────────────────
          var interstateLayer = new FeatureLayer({{
            url: "{interstate_url}",
            title: "Interstates",
            renderer: {{ type: "simple", symbol: {{ type: "simple-line", color: [210, 35, 35], width: 1.8 }} }},
            popupTemplate: {{ title: "Interstate {{ROUTE_NUM}}" }}
          }});

          // ── State highways ────────────────────────────────────────────────────
          var stateHwyLayer = new FeatureLayer({{
            url: "{state_hwy_url}",
            title: "State Highways",
            renderer: {{ type: "simple", symbol: {{ type: "simple-line", color: [220, 140, 0], width: 1.1 }} }},
            popupTemplate: {{ title: "State Hwy {{ROUTE_NUM}}" }}
          }});

          // ── Map + view (without mfg layer yet — added after async fetch) ─────
          var map = new Map({{
            basemap: "gray-vector",
            layers: [dciLayer, countyLayer, stateHwyLayer, interstateLayer]
          }});

          var view = new MapView({{
            container: "viewDiv",
            map: map,
            center: [-98.5, 39.5],
            zoom: 4
          }});

          // ── Mfg decline GeoJSONLayer (county-level, injected from Python) ────
          var COUNTY_GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json";
          fetch(COUNTY_GEOJSON_URL)
            .then(function(r) {{ return r.json(); }})
            .then(function(geojson) {{
              geojson.features.forEach(function(f) {{
                var fips = String(f.id).padStart(5, "0");
                f.properties.mfg_decline = (mfgData[fips] !== undefined) ? mfgData[fips] : null;
              }});
              var blob = new Blob([JSON.stringify(geojson)], {{ type: "application/geo+json" }});
              var mfgLayer = new GeoJSONLayer({{
                url: URL.createObjectURL(blob),
                title: "Mfg. Employment Decline 1991–2011 (pp)",
                opacity: 0.65,
                renderer: {{
                  type: "class-breaks",
                  field: "mfg_decline",
                  legendOptions: {{ title: "Mfg Share Change (pp)" }},
                  defaultSymbol: {{ type: "simple-fill", color: [210,210,210,80], outline: {{ width: 0 }} }},
                  defaultLabel: "No data",
                  classBreakInfos: [
                    {{ minValue: -100, maxValue: -20, label: "< −20 pp (Severe)",  symbol: {{ type: "simple-fill", color: [165, 15, 21, 200], outline: {{ width: 0 }} }} }},
                    {{ minValue:  -20, maxValue: -10, label: "−20 to −10 pp",      symbol: {{ type: "simple-fill", color: [222, 45, 38, 180], outline: {{ width: 0 }} }} }},
                    {{ minValue:  -10, maxValue:  -5, label: "−10 to −5 pp",       symbol: {{ type: "simple-fill", color: [252,146,114, 160], outline: {{ width: 0 }} }} }},
                    {{ minValue:   -5, maxValue:   0, label: "−5 to 0 pp",         symbol: {{ type: "simple-fill", color: [252,187,161, 140], outline: {{ width: 0 }} }} }},
                    {{ minValue:    0, maxValue: 100, label: "≥ 0 pp (No decline)", symbol: {{ type: "simple-fill", color: [186,228,179, 130], outline: {{ width: 0 }} }} }}
                  ]
                }},
                popupTemplate: {{
                  title: "{{name}}",
                  content: "Manufacturing share change (1991–2011): <b>{{mfg_decline}} pp</b>"
                }}
              }});
              map.add(mfgLayer, 0); // insert below DCI layer
            }});

          view.ui.add(new LayerList({{ view: view }}), "top-right");
          view.ui.add(new Legend({{ view: view }}), "bottom-left");
          view.ui.add(new ScaleBar({{ view: view, unit: "dual" }}), "bottom-right");
        }});
      </script>
    </body>
    </html>
    """

components.html(
    _arcgis_map_html(_county_url, _interstate_url, _state_hwy_url, _dci_url, _mfg_decline_json),
    height=650,
    scrolling=False,
)
st.caption(
    "ArcGIS map · **Mfg. Decline** (county, red = larger decline) and "
    "**Community Economic Distress Index** (census tract, yellow→red = more distressed) · "
    "Interstates (red lines) · State Highways (amber lines) · Toggle layers via the LayerList panel."
)

# Styling constants
ROBOTO = "Roboto, sans-serif"
ROBOTO_MED = "Roboto Medium, sans-serif"

SHARED_LAYOUT = dict(
    paper_bgcolor="#F4F4F4",
    plot_bgcolor="#F4F4F4",
    font=dict(family=ROBOTO, color="black"),
    margin=dict(t=110, r=30, l=155, b=100),
)

SHARED_LEGEND = dict(
    font=dict(size=12, color="black", family=ROBOTO),
    bgcolor="#ECECEC",
    bordercolor="black",
    borderwidth=1,
)

# Import shock shading
IMPORT_SHOCK = dict(
    x0=2000, x1=2011, y0=0, y1=1.1,
    xref="x", yref="paper",
    fillcolor="gray", opacity=0.15,
    line_width=0, type="rect",
)

IMPORT_LABEL = dict(
    x=2005.5, y=0.02,
    xref="x", yref="paper",
    text="Import Shock",
    showarrow=False,
    font=dict(size=13, color="black"),
)

def apply_xaxis(fig):
    """Apply consistent x-axis formatting"""
    fig.update_xaxes(
        title=dict(text="Year", font=dict(color="black", size=20, family=ROBOTO_MED)),
        range=[1990, 2023],
        dtick=5,
        title_standoff=30,
        tickfont=dict(color="black", size=20, family=ROBOTO),
        showticklabels=True,
        ticks="outside",
        tickcolor="black",
        linecolor="black",
        linewidth=1,
    )

# SECTION 1: State Filter
st.sidebar.markdown("---")
st.sidebar.write("### Trends Settings")

# Filter for selected state (remove NaN values first)
sorted_states = sorted([s for s in long_df["state"].unique() if pd.notna(s)])

selected_state = st.sidebar.selectbox(
    "Filter to State (optional)",
    options=["All States"] + sorted_states,
)

if selected_state == "All States":
    filtered_long = long_df.copy()
    state_label = "All U.S. Counties"
else:
    filtered_long = long_df[long_df["state"] == selected_state].copy()
    state_label = f"{selected_state} Counties"

# SECTION 2: Animated Bubble Chart – Wage vs Employment (Non-College Workers)
st.subheader("📊 Wage vs Employment Trade-off: Non-College Workers")
_bubble_caption = (
    f"{state_label} · Heat intensity = total non-college workers in each wage/employment bin · Press ▶ or drag the year slider"
    if selected_state == "All States"
    else f"{state_label} · Bubble size = total non-college employment · Press ▶ or drag the year slider"
)
st.caption(_bubble_caption)

# Years for animation (2000–2022)
anim_years = sorted([int(y) for y in long_df["year"].dropna().unique() if 2000 <= y <= 2022])

# Prepare data: filter to animation years and drop missing
anim_data = filtered_long[filtered_long["year"].isin(anim_years)].dropna(
    subset=["star_median", "star_emp_rate", "employed_STARs"]
).copy()

# Compute global axis ranges from all animation data (so no county disappears)
_x_min = anim_data["star_emp_rate"].min()
_x_max = anim_data["star_emp_rate"].max()
_y_min = anim_data["star_median"].min()
_y_max = anim_data["star_median"].max()
_x_pad = (_x_max - _x_min) * 0.03
_y_pad = (_y_max - _y_min) * 0.03
BUBBLE_X_RANGE = [_x_min - _x_pad, _x_max + _x_pad]
BUBBLE_Y_RANGE = [_y_min - _y_pad, _y_max + _y_pad]

# Heatmap bin sizes (fixed so bins are identical across frames)
_N_BINS = 35
HEAT_XBIN_SIZE = (_x_max - _x_min + 2 * _x_pad) / _N_BINS
HEAT_YBIN_SIZE = (_y_max - _y_min + 2 * _y_pad) / _N_BINS

def _bubble_trace(yr_df):
    """Return a Histogram2d (heatmap) for All States, or Scatter for a single state."""
    if selected_state == "All States":
        return go.Histogram2d(
            x=yr_df["star_emp_rate"],
            y=yr_df["star_median"],
            z=yr_df["employed_STARs"],
            histfunc="sum",
            xbins=dict(start=BUBBLE_X_RANGE[0], end=BUBBLE_X_RANGE[1], size=HEAT_XBIN_SIZE),
            ybins=dict(start=BUBBLE_Y_RANGE[0], end=BUBBLE_Y_RANGE[1], size=HEAT_YBIN_SIZE),
            colorscale="YlOrRd",
            reversescale=False,
            colorbar=dict(
                title=dict(text="County Workers", font=dict(family=ROBOTO, size=13), side="top"),
                tickformat=",.0f",
            ),
            zmin=0,
            name="County Density",
            hovertemplate="Emp Rate: %{x:.1f}%<br>Wage: $%{y:,.0f}<br>Workers: %{z:,.0f}<extra></extra>",
        )
    else:
        return go.Scatter(
            x=yr_df["star_emp_rate"],
            y=yr_df["star_median"],
            mode="markers",
            marker=dict(
                size=np.sqrt(yr_df["employed_STARs"] / 100) + 5,
                color="#445E93",
                opacity=0.6,
                line=dict(width=1, color="black"),
            ),
            text=[
                f"{n}<br>Wage: ${w:,.0f}<br>Emp Rate: {e:.1f}%<br>Workers: {emp:,.0f}"
                for n, w, e, emp in zip(
                    yr_df["name_short"], yr_df["star_median"],
                    yr_df["star_emp_rate"], yr_df["employed_STARs"]
                )
            ],
            hoverinfo="text",
            name="Counties",
        )

# Build animation frames
bubble_frames = [
    go.Frame(data=[_bubble_trace(anim_data[anim_data["year"] == yr])], name=str(yr))
    for yr in anim_years
]

# Initial frame (first year)
init_df = anim_data[anim_data["year"] == anim_years[0]]

fig_bubble = go.Figure(
    data=[_bubble_trace(init_df)],
    frames=bubble_frames,
)

fig_bubble.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Median Non-College Wage and Employment Rate <br> Across all Counties",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    xaxis=dict(
        title=dict(text="County Non-College Employment Rate (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        range=BUBBLE_X_RANGE,
        tickfont=dict(color="black", size=18, family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="County Non-College Median Wage ($)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        range=BUBBLE_Y_RANGE,
        tickformat="$,.0f",
        tickfont=dict(color="black", size=18, family=ROBOTO),
    ),
    hovermode="closest",
    height=650,
    updatemenus=[dict(
        type="buttons",
        showactive=False,
        x=0.5, xanchor="center",
        y=-0.30, yanchor="top",
        buttons=[
            dict(
                label="▶ Play",
                method="animate",
                args=[None, {"frame": {"duration": 600, "redraw": True},
                             "fromcurrent": True,
                             "transition": {"duration": 200}}],
            ),
            dict(
                label="⏸ Pause",
                method="animate",
                args=[[None], {"frame": {"duration": 0, "redraw": False},
                               "mode": "immediate",
                               "transition": {"duration": 0}}],
            ),
        ],
        font=dict(size=14, family=ROBOTO),
    )],
    sliders=[dict(
        active=0,
        pad=dict(t=55, b=10),
        x=0.05, len=0.9,
        steps=[
            dict(
                args=[[str(yr)], {"frame": {"duration": 300, "redraw": True},
                                  "mode": "immediate",
                                  "transition": {"duration": 200}}],
                label=str(yr),
                method="animate",
            )
            for yr in anim_years
        ],
    )],
)

fig_bubble.update_layout(margin=dict(t=110, r=30, l=155, b=240))

# Annotate total non-college workers (most recent year) — bottom-right, under colorbar
_total_workers_ref = int(anim_data[anim_data["year"] == anim_years[-1]]["employed_STARs"].sum())
fig_bubble.add_annotation(
    text=f"Total non-college workers ({anim_years[-1]}): {_total_workers_ref:,}",
    xref="paper", yref="paper",
    x=1.1, y=-0.6,
    xanchor="right", yanchor="top",
    showarrow=False,
    font=dict(size=12, color="#666666", family=ROBOTO),
)

st.plotly_chart(fig_bubble, width='stretch')

# SECTION 3: National Trend – Aggregated Metrics
st.subheader("📈 National Trends: Aggregated Across All Counties")

# Compute national aggregates by summing across counties
national_agg = long_df.groupby("year").agg({
    "employed_STARs": "sum",
    "employed_college": "sum",
    "total_workers": "sum",
    "star_middle_count": "sum",
    "star_upper_count": "sum",
}).reset_index()

# Calculate national-level rates
national_agg["star_emp_rate_national"] = (
    national_agg["employed_STARs"] / long_df.groupby("year")["workagepop_STARS"].sum().values * 100
)
national_agg["college_emp_rate_national"] = (
    national_agg["employed_college"] / long_df.groupby("year")["total_college"].sum().values * 100
)
national_agg["pct_star_midupp"] = (
    (national_agg["star_middle_count"] + national_agg["star_upper_count"]) / 
    national_agg["employed_STARs"] * 100
)

# National wage trends
national_wage = long_df.groupby("year").agg({
    "star_median": "mean",
    "college_median": "mean",
}).reset_index()

# Combine
national_agg = national_agg.merge(national_wage, on="year")
national_agg["wage_ratio"] = national_agg["college_median"] / national_agg["star_median"]

# County-level percentile distributions for national trend tabs
_long_nat = long_df.copy()
_long_nat["college_emp_rate"] = (
    _long_nat["employed_college"] / _long_nat["total_college"].replace(0, np.nan) * 100
)
nat_pct = _long_nat.groupby("year").agg(
    emp_nc_10=("star_emp_rate",    lambda x: x.quantile(0.10)),
    emp_nc_25=("star_emp_rate",    lambda x: x.quantile(0.25)),
    emp_nc_50=("star_emp_rate",    lambda x: x.quantile(0.50)),
    emp_nc_75=("star_emp_rate",    lambda x: x.quantile(0.75)),
    emp_nc_90=("star_emp_rate",    lambda x: x.quantile(0.90)),
    emp_col_10=("college_emp_rate", lambda x: x.quantile(0.10)),
    emp_col_25=("college_emp_rate", lambda x: x.quantile(0.25)),
    emp_col_50=("college_emp_rate", lambda x: x.quantile(0.50)),
    emp_col_75=("college_emp_rate", lambda x: x.quantile(0.75)),
    emp_col_90=("college_emp_rate", lambda x: x.quantile(0.90)),
    midupp_10=("pct_star_midupp",   lambda x: x.quantile(0.10)),
    midupp_25=("pct_star_midupp",   lambda x: x.quantile(0.25)),
    midupp_50=("pct_star_midupp",   lambda x: x.quantile(0.50)),
    midupp_75=("pct_star_midupp",   lambda x: x.quantile(0.75)),
    midupp_90=("pct_star_midupp",   lambda x: x.quantile(0.90)),
    wage_nc_10=("star_median",      lambda x: x.quantile(0.10)),
    wage_nc_25=("star_median",      lambda x: x.quantile(0.25)),
    wage_nc_50=("star_median",      lambda x: x.quantile(0.50)),
    wage_nc_75=("star_median",      lambda x: x.quantile(0.75)),
    wage_nc_90=("star_median",      lambda x: x.quantile(0.90)),
    wage_col_10=("college_median",  lambda x: x.quantile(0.10)),
    wage_col_25=("college_median",  lambda x: x.quantile(0.25)),
    wage_col_50=("college_median",  lambda x: x.quantile(0.50)),
    wage_col_75=("college_median",  lambda x: x.quantile(0.75)),
    wage_col_90=("college_median",  lambda x: x.quantile(0.90)),
).reset_index()

def _add_pct_bands(fig, df, p10, p25, p50, p75, p90, fill_light, fill_dark, line_color, label):
    fig.add_trace(go.Scatter(x=df["year"], y=df[p90], fill=None, mode="lines", line_color="rgba(0,0,0,0)", showlegend=False))
    fig.add_trace(go.Scatter(x=df["year"], y=df[p10], fill="tonexty", mode="lines", line_color="rgba(0,0,0,0)", fillcolor=fill_light, name=f"{label}: 10–90th pct"))
    fig.add_trace(go.Scatter(x=df["year"], y=df[p75], fill=None, mode="lines", line_color="rgba(0,0,0,0)", showlegend=False))
    fig.add_trace(go.Scatter(x=df["year"], y=df[p25], fill="tonexty", mode="lines", line_color="rgba(0,0,0,0)", fillcolor=fill_dark, name=f"{label}: 25–75th pct"))
    fig.add_trace(go.Scatter(x=df["year"], y=df[p50], mode="lines", line=dict(color=line_color, width=2.5, dash="dash"), name=f"{label} Median"))

# Tab layout for national trends
tab1, tab2, tab3, tab4 = st.tabs(
    ["Employment Rates", "Mid/Upper Income Jobs", "Median Wages", "Wage Ratio (College/Non-College)"]
)

# Tab 1: Employment Rates – county distribution bands
with tab1:
    fig_emp = go.Figure()
    _add_pct_bands(fig_emp, nat_pct,
        "emp_nc_10", "emp_nc_25", "emp_nc_50", "emp_nc_75", "emp_nc_90",
        "rgba(247,160,114,0.2)", "rgba(247,160,114,0.5)", "#F7A072", "Non-College")
    _add_pct_bands(fig_emp, nat_pct,
        "emp_col_10", "emp_col_25", "emp_col_50", "emp_col_75", "emp_col_90",
        "rgba(68,94,147,0.2)", "rgba(68,94,147,0.5)", "#445E93", "College")
    fig_emp.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="Employment Rate Distribution Across Counties",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Employment Rate (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25,
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND,
        height=500,
    )
    apply_xaxis(fig_emp)
    fig_emp.add_shape(**IMPORT_SHOCK)
    fig_emp.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_emp, width='stretch')

# Tab 2: Mid/Upper Income Share – county distribution bands
with tab2:
    fig_midupp = go.Figure()
    _add_pct_bands(fig_midupp, nat_pct,
        "midupp_10", "midupp_25", "midupp_50", "midupp_75", "midupp_90",
        "rgba(44,160,44,0.2)", "rgba(44,160,44,0.5)", "#2CA02C", "Non-College Mid/Upper")
    fig_midupp.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="Non-College Mid/Upper Income Share Distribution Across Counties",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Percent of Non-College Workers (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25,
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND,
        height=500,
    )
    apply_xaxis(fig_midupp)
    fig_midupp.add_shape(**IMPORT_SHOCK)
    fig_midupp.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_midupp, width='stretch')

# Tab 3: Median Wages – county distribution bands
with tab3:
    fig_wage = go.Figure()
    _add_pct_bands(fig_wage, nat_pct,
        "wage_nc_10", "wage_nc_25", "wage_nc_50", "wage_nc_75", "wage_nc_90",
        "rgba(247,160,114,0.2)", "rgba(247,160,114,0.5)", "#F7A072", "Non-College")
    _add_pct_bands(fig_wage, nat_pct,
        "wage_col_10", "wage_col_25", "wage_col_50", "wage_col_75", "wage_col_90",
        "rgba(68,94,147,0.2)", "rgba(68,94,147,0.5)", "#445E93", "College")
    fig_wage.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="Median Wage Distribution Across Counties",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Median Wage ($)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25,
            tickformat="$,.0f",
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND,
        height=500,
    )
    apply_xaxis(fig_wage)
    fig_wage.add_shape(**IMPORT_SHOCK)
    fig_wage.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_wage, width='stretch')

# Tab 4: College/Non-College Wage Ratio – county distribution
with tab4:
    # Compute per-county wage ratio, then percentile bands across counties by year
    long_df["wage_ratio"] = long_df["college_median"] / long_df["star_median"]
    ratio_pct = long_df.groupby("year").agg(
        ratio_10=("wage_ratio", lambda x: x.quantile(0.10)),
        ratio_25=("wage_ratio", lambda x: x.quantile(0.25)),
        ratio_50=("wage_ratio", lambda x: x.quantile(0.50)),
        ratio_75=("wage_ratio", lambda x: x.quantile(0.75)),
        ratio_90=("wage_ratio", lambda x: x.quantile(0.90)),
    ).reset_index()

    fig_ratio = go.Figure()

    fig_ratio.add_trace(go.Scatter(
        x=ratio_pct["year"], y=ratio_pct["ratio_90"],
        fill=None, mode="lines", line_color="rgba(0,0,0,0)", showlegend=False,
    ))
    fig_ratio.add_trace(go.Scatter(
        x=ratio_pct["year"], y=ratio_pct["ratio_10"],
        fill="tonexty", mode="lines", line_color="rgba(0,0,0,0)",
        fillcolor="rgba(139, 26, 139, 0.15)", name="10–90th percentile",
    ))
    fig_ratio.add_trace(go.Scatter(
        x=ratio_pct["year"], y=ratio_pct["ratio_75"],
        fill=None, mode="lines", line_color="rgba(0,0,0,0)", showlegend=False,
    ))
    fig_ratio.add_trace(go.Scatter(
        x=ratio_pct["year"], y=ratio_pct["ratio_25"],
        fill="tonexty", mode="lines", line_color="rgba(0,0,0,0)",
        fillcolor="rgba(139, 26, 139, 0.45)", name="25–75th percentile (middle 50%)",
    ))
    fig_ratio.add_trace(go.Scatter(
        x=ratio_pct["year"], y=ratio_pct["ratio_50"],
        mode="lines", line=dict(color="black", width=2, dash="dash"), name="Median",
    ))

    fig_ratio.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="College/Non-College Wage Ratio Distribution Across Counties",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Ratio (College Wage / Non-College Wage)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25,
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND,
        height=500,
    )
    apply_xaxis(fig_ratio)
    fig_ratio.add_shape(**IMPORT_SHOCK)
    fig_ratio.add_annotation(**IMPORT_LABEL)

    st.plotly_chart(fig_ratio, width='stretch')

# SECTION 4: County Percentile Distribution Over Time
st.subheader("📊 County Dispersion: Percentile Bands Over Time")
st.caption("Shows range of county outcomes – darker band = middle 50% of counties")

# Calculate percentiles by year for non-college metrics
percentiles_by_year = long_df.groupby("year").agg({
    "star_emp_rate": [lambda x: x.quantile(0.10), lambda x: x.quantile(0.25), 
                      lambda x: x.quantile(0.50), lambda x: x.quantile(0.75),
                      lambda x: x.quantile(0.90)],
    "star_median": [lambda x: x.quantile(0.10), lambda x: x.quantile(0.25),
                    lambda x: x.quantile(0.50), lambda x: x.quantile(0.75),
                    lambda x: x.quantile(0.90)],
}).reset_index()

# Flatten column names
percentiles_by_year.columns = ["year", 
    "emp_10", "emp_25", "emp_50", "emp_75", "emp_90",
    "wage_10", "wage_25", "wage_50", "wage_75", "wage_90"
]

# Employment percentile chart
fig_emp_pct = go.Figure()

fig_emp_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["emp_90"],
    fill=None,
    mode="lines",
    line_color="rgba(0,0,0,0)",
))
fig_emp_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["emp_10"],
    fill="tonexty",
    mode="lines",
    line_color="rgba(0,0,0,0)",
    fillcolor="rgba(244, 160, 114, 0.2)",
    name="10–90th percentile",
))

fig_emp_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["emp_75"],
    fill=None,
    mode="lines",
    line_color="rgba(0,0,0,0)",
))
fig_emp_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["emp_25"],
    fill="tonexty",
    mode="lines",
    line_color="rgba(0,0,0,0)",
    fillcolor="rgba(68, 94, 147, 0.5)",
    name="25–75th percentile (middle 50%)",
))

fig_emp_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["emp_50"],
    mode="lines",
    line=dict(color="black", width=2, dash="dash"),
    name="Median",
))

fig_emp_pct.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Non-College Employment Rate Distribution Across Counties",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Non-College Employment Rate (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        tickfont=dict(color="black", size=18, family=ROBOTO),
    ),
    legend=SHARED_LEGEND,
    height=550,
)
apply_xaxis(fig_emp_pct)
fig_emp_pct.add_shape(**IMPORT_SHOCK)
fig_emp_pct.add_annotation(**IMPORT_LABEL)

st.plotly_chart(fig_emp_pct, width='stretch')

# Wage percentile chart
fig_wage_pct = go.Figure()

fig_wage_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["wage_90"],
    fill=None,
    mode="lines",
    line_color="rgba(0,0,0,0)",
))
fig_wage_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["wage_10"],
    fill="tonexty",
    mode="lines",
    line_color="rgba(0,0,0,0)",
    fillcolor="rgba(244, 160, 114, 0.2)",
    name="10–90th percentile",
))

fig_wage_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["wage_75"],
    fill=None,
    mode="lines",
    line_color="rgba(0,0,0,0)",
))
fig_wage_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["wage_25"],
    fill="tonexty",
    mode="lines",
    line_color="rgba(0,0,0,0)",
    fillcolor="rgba(68, 94, 147, 0.5)",
    name="25–75th percentile (middle 50%)",
))

fig_wage_pct.add_trace(go.Scatter(
    x=percentiles_by_year["year"],
    y=percentiles_by_year["wage_50"],
    mode="lines",
    line=dict(color="black", width=2, dash="dash"),
    name="Median",
))

fig_wage_pct.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Non-College Median Wage Distribution Across Counties",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Non-College Median Wage ($)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        tickformat="$,.0f",
        tickfont=dict(color="black", size=18, family=ROBOTO),
    ),
    legend=SHARED_LEGEND,
    height=550,
)
apply_xaxis(fig_wage_pct)
fig_wage_pct.add_shape(**IMPORT_SHOCK)
fig_wage_pct.add_annotation(**IMPORT_LABEL)

st.plotly_chart(fig_wage_pct, width='stretch')

# SECTION 5: County Convergence/Divergence Analysis
st.subheader("📉 Convergence Analysis: Inequality Across Counties")
st.caption("Coefficient of Variation measures dispersion – rising CV = counties diverging")

# Calculate coefficient of variation by year
cv_by_year = long_df.groupby("year").agg({
    "star_emp_rate": lambda x: (x.std() / x.mean() * 100) if x.mean() != 0 else 0,
    "star_median": lambda x: (x.std() / x.mean() * 100) if x.mean() != 0 else 0,
    "pct_star_midupp": lambda x: (x.std() / x.mean() * 100) if x.mean() != 0 else 0,
}).reset_index()

cv_by_year.columns = ["year", "emp_cv", "wage_cv", "midupp_cv"]

fig_cv = go.Figure()

fig_cv.add_trace(go.Scatter(
    x=cv_by_year["year"],
    y=cv_by_year["emp_cv"],
    mode="lines",
    line=dict(color="#F7A072", width=3),
    name="Employment Rate CV",
))
fig_cv.add_trace(go.Scatter(
    x=cv_by_year["year"],
    y=cv_by_year["wage_cv"],
    mode="lines",
    line=dict(color="#445E93", width=3),
    name="Median Wage CV",
))
fig_cv.add_trace(go.Scatter(
    x=cv_by_year["year"],
    y=cv_by_year["midupp_cv"],
    mode="lines",
    line=dict(color="#2CA02C", width=3),
    name="Mid/Upper Income CV",
))

fig_cv.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="County Economic Inequality: Coefficient of Variation Over Time",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Coefficient of Variation (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        tickfont=dict(color="black", size=18, family=ROBOTO),
    ),
    legend=SHARED_LEGEND,
    height=500,
)
apply_xaxis(fig_cv)
fig_cv.add_shape(**IMPORT_SHOCK)
fig_cv.add_annotation(**IMPORT_LABEL)

st.plotly_chart(fig_cv, width = 'stretch')

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Trends by China Shock Exposure (Quartiles)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🌏 Trends by China Shock Exposure (County Quartiles)")
st.caption(
    "Counties grouped into quartiles by China shock intensity "
    "(predicted job loss per worker). Q1 = least exposed, Q4 = most exposed."
)

QUARTILE_COLORS = {
    "Q1 (Lowest)": "#2CA02C",
    "Q2":          "#1F77B4",
    "Q3":          "#FF7F0E",
    "Q4 (Highest)":"#D62728",
}
QUARTILE_ORDER = ["Q1 (Lowest)", "Q2", "Q3", "Q4 (Highest)"]

# ── Build aggregates by year × quartile ──────────────────────────────────────
shock_long = long_df.dropna(subset=["china_shock_q"]).copy()

shock_agg_raw = shock_long.groupby(["year", "china_shock_q"], observed=True).agg(
    employed_STARs=("employed_STARs", "sum"),
    employed_college=("employed_college", "sum"),
    workagepop_STARS=("workagepop_STARS", "sum"),
    total_college=("total_college", "sum"),
    star_middle_count=("star_middle_count", "sum"),
    star_upper_count=("star_upper_count", "sum"),
    star_median=("star_median", "mean"),
    college_median=("college_median", "mean"),
).reset_index()

shock_agg_raw["star_emp_rate"] = (
    shock_agg_raw["employed_STARs"] / shock_agg_raw["workagepop_STARS"] * 100
)
shock_agg_raw["college_emp_rate"] = (
    shock_agg_raw["employed_college"] / shock_agg_raw["total_college"] * 100
)
shock_agg_raw["pct_star_midupp"] = (
    (shock_agg_raw["star_middle_count"] + shock_agg_raw["star_upper_count"])
    / shock_agg_raw["employed_STARs"] * 100
)
shock_agg_raw["wage_ratio"] = shock_agg_raw["college_median"] / shock_agg_raw["star_median"]

# ── Tabs for quartile national aggregates ────────────────────────────────────
sq_tab1, sq_tab2, sq_tab3, sq_tab4 = st.tabs([
    "Employment Rates", "Mid/Upper Income Jobs", "Median Wages", "Wage Ratio"
])

def _add_quartile_lines(fig, df, y_col):
    for q in QUARTILE_ORDER:
        sub = df[df["china_shock_q"] == q]
        fig.add_trace(go.Scatter(
            x=sub["year"], y=sub[y_col],
            mode="lines",
            line=dict(color=QUARTILE_COLORS[q], width=2.5),
            name=q,
        ))

with sq_tab1:
    fig_sq_emp = go.Figure()
    _add_quartile_lines(fig_sq_emp, shock_agg_raw, "star_emp_rate")
    fig_sq_emp.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="Non-College Employment Rate by China Shock Quartile",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Non-College Employment Rate (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25, dtick=2,
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND, height=500,
    )
    apply_xaxis(fig_sq_emp)
    fig_sq_emp.add_shape(**IMPORT_SHOCK)
    fig_sq_emp.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_sq_emp, width='stretch')

with sq_tab2:
    fig_sq_midupp = go.Figure()
    _add_quartile_lines(fig_sq_midupp, shock_agg_raw, "pct_star_midupp")
    fig_sq_midupp.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="Non-College Mid/Upper Income Share by China Shock Quartile",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Percent of Non-College Workers (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25, range=[0, 100],
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND, height=500,
    )
    apply_xaxis(fig_sq_midupp)
    fig_sq_midupp.add_shape(**IMPORT_SHOCK)
    fig_sq_midupp.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_sq_midupp, width='stretch')

with sq_tab3:
    fig_sq_wage = go.Figure()
    _add_quartile_lines(fig_sq_wage, shock_agg_raw, "star_median")
    fig_sq_wage.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="Non-College Median Wage by China Shock Quartile",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Non-College Median Wage ($)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25, tickformat="$,.0f",
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND, height=500,
    )
    apply_xaxis(fig_sq_wage)
    fig_sq_wage.add_shape(**IMPORT_SHOCK)
    fig_sq_wage.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_sq_wage, width='stretch')

with sq_tab4:
    fig_sq_ratio = go.Figure()
    _add_quartile_lines(fig_sq_ratio, shock_agg_raw, "wage_ratio")
    fig_sq_ratio.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text="College/Non-College Wage Ratio by China Shock Quartile",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Ratio (College / Non-College Wage)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25,
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND, height=500,
    )
    apply_xaxis(fig_sq_ratio)
    fig_sq_ratio.add_shape(**IMPORT_SHOCK)
    fig_sq_ratio.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_sq_ratio, width='stretch')

# ── Median trends by quartile (replaces percentile band section) ─────────────
st.markdown("#### County Median Trends by China Shock Quartile")
st.caption("Median (50th percentile) across counties within each shock quartile")

shock_median = shock_long.groupby(["year", "china_shock_q"], observed=True).agg(
    emp_50=("star_emp_rate", "median"),
    wage_50=("star_median", "median"),
).reset_index()

fig_sq_emp_med = go.Figure()
fig_sq_wage_med = go.Figure()
for q in QUARTILE_ORDER:
    sub = shock_median[shock_median["china_shock_q"] == q]
    fig_sq_emp_med.add_trace(go.Scatter(
        x=sub["year"], y=sub["emp_50"],
        mode="lines", line=dict(color=QUARTILE_COLORS[q], width=2.5), name=q,
    ))
    fig_sq_wage_med.add_trace(go.Scatter(
        x=sub["year"], y=sub["wage_50"],
        mode="lines", line=dict(color=QUARTILE_COLORS[q], width=2.5), name=q,
    ))

for fig, title, ytitle, yfmt in [
    (fig_sq_emp_med,
     "Median Non-College Employment Rate by Shock Quartile",
     "Non-College Employment Rate (%)", None),
    (fig_sq_wage_med,
     "Median Non-College Wage by Shock Quartile",
     "Non-College Median Wage ($)", "$,.0f"),
]:
    yaxis_cfg = dict(
        title=dict(text=ytitle, font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        tickfont=dict(color="black", size=18, family=ROBOTO),
    )
    if yfmt:
        yaxis_cfg["tickformat"] = yfmt
    fig.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text=title, x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=yaxis_cfg,
        legend=SHARED_LEGEND, height=500,
    )
    apply_xaxis(fig)
    fig.add_shape(**IMPORT_SHOCK)
    fig.add_annotation(**IMPORT_LABEL)

st.plotly_chart(fig_sq_emp_med, width='stretch')
st.plotly_chart(fig_sq_wage_med, width='stretch')

# ── CV by quartile ────────────────────────────────────────────────────────────
st.markdown("#### Coefficient of Variation by China Shock Quartile")
st.caption("Rising CV within a quartile = counties in that group diverging further")

cv_by_shock = shock_long.groupby(["year", "china_shock_q"], observed=True).agg(
    emp_cv=("star_emp_rate",   lambda x: x.std() / x.mean() * 100 if x.mean() != 0 else 0),
    wage_cv=("star_median",    lambda x: x.std() / x.mean() * 100 if x.mean() != 0 else 0),
    midupp_cv=("pct_star_midupp", lambda x: x.std() / x.mean() * 100 if x.mean() != 0 else 0),
).reset_index()

for cv_col, cv_label, cv_color_base in [
    ("emp_cv",   "Employment Rate CV",     "#F7A072"),
    ("wage_cv",  "Median Wage CV",         "#445E93"),
    ("midupp_cv","Mid/Upper Income CV",    "#2CA02C"),
]:
    fig_cv_q = go.Figure()
    for q in QUARTILE_ORDER:
        sub = cv_by_shock[cv_by_shock["china_shock_q"] == q]
        fig_cv_q.add_trace(go.Scatter(
            x=sub["year"], y=sub[cv_col],
            mode="lines", line=dict(color=QUARTILE_COLORS[q], width=2.5), name=q,
        ))
    fig_cv_q.update_layout(
        **SHARED_LAYOUT,
        title=dict(
            text=f"{cv_label} by China Shock Quartile",
            x=0.5, y=0.94, xanchor="center", yanchor="top",
            font=dict(size=21, color="black", family=ROBOTO),
        ),
        yaxis=dict(
            title=dict(text="Coefficient of Variation (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
            title_standoff=25,
            tickfont=dict(color="black", size=18, family=ROBOTO),
        ),
        legend=SHARED_LEGEND, height=500,
    )
    apply_xaxis(fig_cv_q)
    fig_cv_q.add_shape(**IMPORT_SHOCK)
    fig_cv_q.add_annotation(**IMPORT_LABEL)
    st.plotly_chart(fig_cv_q, width='stretch')

# SECTION 7: Data Export
with st.expander("📥 Download Trend Data"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = national_agg.to_csv(index=False)
        st.download_button(
            label="National Aggregates (CSV)",
            data=csv,
            file_name="national_trends.csv",
            mime="text/csv",
        )
    
    with col2:
        csv = percentiles_by_year.to_csv(index=False)
        st.download_button(
            label="County Percentiles (CSV)",
            data=csv,
            file_name="county_percentiles.csv",
            mime="text/csv",
        )
    
    with col3:
        csv = cv_by_year.to_csv(index=False)
        st.download_button(
            label="Convergence Data (CSV)",
            data=csv,
            file_name="convergence_analysis.csv",
            mime="text/csv",
        )
