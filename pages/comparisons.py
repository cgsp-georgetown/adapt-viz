"""
County Comparison Page
Compare 24 counties side by side on:
  1. Manufacturing Share & Non-College Mid/Upper Income Jobs
  2. Median Wage
  3. Total Employment
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="County Comparison", page_icon="", layout="wide")

# Custom font styling
streamlit_style = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@100;400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
    </style>
"""
st.markdown(streamlit_style, unsafe_allow_html=True)

# Color palette for up to 4 counties
COLORS = ["#F7A072", "#445E93", "#2CA02C", "#9467BD"]

# Load and cache datasets
@st.cache_data
def load_data():
    national_df = pd.read_stata("county_all_vars_index.dta")
    long_df      = pd.read_csv("county_all_vars_post_index.csv")
    return national_df, long_df

national_df, long_df = load_data()

# Sidebar: county selection interface
st.sidebar.write("## County Comparison Settings")

num_counties = st.sidebar.radio(
    "How many counties to compare?",
    options=[2, 3, 4],
    horizontal=True,
)

# Default counties for quick selection
DEFAULTS = [
    ("NC", "Durham County, NC"),    # knowledge economy, good contrast
    ("NC", "Catawba County, NC"),   # furniture/textiles, China shock
    ("NC", "Gaston County, NC"),    # textiles/apparel, China shock
    ("NC", "Randolph County, NC"),  # furniture, China shock
]

selections = []   # list of (state, county) tuples
sorted_states = np.sort(national_df["state"].unique())

# Build state and county selectors for each comparison slot
for i in range(num_counties):
    st.sidebar.markdown(f"---\n**County {i + 1}**")

    default_state, default_county = DEFAULTS[i]

    # State selector with default index
    try:
        default_state_idx = int(np.where(sorted_states == default_state)[0][0])
    except IndexError:
        default_state_idx = 0

    state = st.sidebar.selectbox(
        f"State #{i + 1}",
        options=sorted_states,
        index=default_state_idx,
        key=f"state_{i}",
    )

    # County selector filtered by state, with default index
    counties_in_state = np.sort(
        national_df.loc[national_df["state"] == state, "county_name"].unique()
    )
    try:
        default_county_idx = int(np.where(counties_in_state == default_county)[0][0])
    except IndexError:
        default_county_idx = 0

    county = st.sidebar.selectbox(
        f"County #{i + 1}",
        options=counties_in_state,
        index=default_county_idx,
        key=f"county_{i}",
    )
    selections.append((state, county))

# Extract long-form data for each selected county
county_long_dfs = []
labels          = []

for state, county in selections:
    df = long_df[long_df["county_name"] == county].copy()
    county_long_dfs.append(df)

    # Use short name from data if available, otherwise construct from county name
    if "name_short" in df.columns and not df.empty:
        label = df["name_short"].iloc[0]
    else:
        label = f"{county}, {state}"
    labels.append(label)

# Page header
st.title("County Economic Comparison")
st.caption("Comparing selected counties  2022 Values, in ")

# Shared styling for all charts
ROBOTO       = "Roboto, sans-serif"
ROBOTO_MED   = "Roboto Medium, sans-serif"

SHARED_XAXIS = dict(
    title=dict(text="Year", font=dict(color="black", size=20, family=ROBOTO_MED)),
    range=[1990, 2023],
    dtick=5,
    title_standoff=30,
    ticklabelposition="outside right",
    tickfont=dict(color="black", size=20, family=ROBOTO),
)

SHARED_LEGEND = dict(
    font=dict(size=14, color="black", family=ROBOTO),
    bgcolor="#ECECEC",
    bordercolor="black",
    borderwidth=1,
)

SHARED_LAYOUT = dict(
    paper_bgcolor="#F4F4F4",
    plot_bgcolor="#F4F4F4",
    font=dict(family=ROBOTO, color="black"),
    margin=dict(t=110, r=30, l=155, b=100),
)

# Import shock shading (20002011) and label
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

# Apply consistent x-axis formatting across all figures
def apply_xaxis(fig):
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

# 
# Chart 1  Manufacturing Share & Non-College Mid/Upper Income Jobs
# 
st.subheader("Manufacturing Share & Non-College Mid/Upper Income Jobs")

fig1 = go.Figure()
fig1.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Manufacturing Share & Non-College Mid/Upper Income Jobs",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Percent of Total (%)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        range=[0.0, 100],
        title_standoff=25,
        tickfont=dict(color="black", size=18, family=ROBOTO),
    ),
    legend=dict(
        orientation="h",
        x=0.5, xanchor="center",
        y=-0.55, yanchor="top",
        entrywidth=250,           # px per entry  forces wrapping
        **SHARED_LEGEND)
)
apply_xaxis(fig1)
fig1.add_shape(**IMPORT_SHOCK)
fig1.add_annotation(**IMPORT_LABEL)

# Add manufacturing share (solid) and mid/upper income jobs (dotted) traces
for df, label, color in zip(county_long_dfs, labels, COLORS):
    if df.empty:
        continue
    df = df.copy()
    if "mfgsh" in df.columns:
        df["mfgsh_pct"] = df["mfgsh"] * 100
        fig1.add_trace(go.Scatter(
            x=df["year"],
            y=df["mfgsh_pct"],
            mode="lines",
            line=dict(color=color, width=3, dash="solid"),
            name=f"{label}  Mfg Share",
        ))
    if "pct_star_midupp" in df.columns:
        fig1.add_trace(go.Scatter(
            x=df["year"],
            y=df["pct_star_midupp"],
            mode="lines",
            line=dict(color=color, width=3, dash="dot"),
            name=f"{label}  Mid/Upper Jobs",
        ))

st.plotly_chart(fig1, width="stretch")
st.caption("Solid lines = Manufacturing Share  Dotted lines = Non-College Mid/Upper Income Jobs")

# 
# Chart 2  Non-College Median Wage
# 
st.subheader("Non-College Median Wage")

fig2 = go.Figure()
fig2.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Non-College Median Wage by County",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Median Wage ($)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        dtick=2500,
        tickfont=dict(color="black", size=18, family=ROBOTO),
        tickformat="$,.0f",
    ),
    legend=dict(
        orientation="h",
        x=0.5, xanchor="center",
        y=-0.50, yanchor="top",
        entrywidth=150,           # px per entry  forces wrapping
        **SHARED_LEGEND)
)
apply_xaxis(fig2)
fig2.add_shape(**IMPORT_SHOCK)
fig2.add_annotation(**IMPORT_LABEL)

# Add median wage traces for each county
for df, label, color in zip(county_long_dfs, labels, COLORS):
    if df.empty:
        continue
    wage_col = "star_median"
    if wage_col:
        fig2.add_trace(go.Scatter(
            x=df["year"],
            y=df[wage_col],
            mode="lines",
            line=dict(color=color, width=3),
            name=label,
        ))

st.plotly_chart(fig2, width="stretch")

# 
# Chart 3  Non-College Employment
# 
st.subheader("Non-College Employment")

fig3 = go.Figure()
fig3.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Non-College Employment by County",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Number Non-College Educated Working", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        tickfont=dict(color="black", size=18, family=ROBOTO),
        tickformat=",",
    ),
    legend=dict(
        orientation="h",
        x=0.5, xanchor="center",
        y=-0.45, yanchor="top",
        entrywidth=150,           # px per entry  forces wrapping
        **SHARED_LEGEND)
)
apply_xaxis(fig3)
fig3.add_shape(**IMPORT_SHOCK)
fig3.add_annotation(**IMPORT_LABEL)

# Add employment traces for each county
for df, label, color in zip(county_long_dfs, labels, COLORS):
    if df.empty:
        continue
    emp_col = "employed_STARs"
    if emp_col:
        fig3.add_trace(go.Scatter(
            x=df["year"],
            y=df[emp_col],
            mode="lines",
            line=dict(color=color, width=3),
            name=label,
        ))

st.plotly_chart(fig3, width="stretch")

# ─────────────────────────────────────────────────────────────────────────────
# Chart 4 – Combined Wages & Employment
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Non-College Median Wage & Employment (Combined)")

fig4 = go.Figure()
fig4.update_layout(
    **SHARED_LAYOUT,
    title=dict(
        text="Non-College Median Wage & Employment by County",
        x=0.5, y=0.94, xanchor="center", yanchor="top",
        font=dict(size=21, color="black", family=ROBOTO),
    ),
    yaxis=dict(
        title=dict(text="Median Wage ($)", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        dtick=2500,
        tickfont=dict(color="black", size=18, family=ROBOTO),
        tickformat="$,.0f",
    ),
    yaxis2=dict(
        title=dict(text="Number Non-College Educated Working", font=dict(color="black", size=20, family=ROBOTO_MED)),
        title_standoff=25,
        tickfont=dict(color="black", size=18, family=ROBOTO),
        tickformat=",",
        overlaying="y",
        side="right",
    ),
    legend=dict(
        orientation="h",
        x=0.5, xanchor="center",
        y=-0.55, yanchor="top",
        entrywidth=220,
        **SHARED_LEGEND,
    ),
)
fig4.update_layout(margin=dict(t=110, r=155, l=155, b=120))
apply_xaxis(fig4)
fig4.add_shape(**IMPORT_SHOCK)
fig4.add_annotation(**IMPORT_LABEL)

for df, label, color in zip(county_long_dfs, labels, COLORS):
    if df.empty:
        continue
    if "star_median" in df.columns:
        fig4.add_trace(go.Scatter(
            x=df["year"],
            y=df["star_median"],
            mode="lines",
            line=dict(color=color, width=3, dash="solid"),
            name=f"{label}  Wage",
            yaxis="y1",
        ))
    if "employed_STARs" in df.columns:
        fig4.add_trace(go.Scatter(
            x=df["year"],
            y=df["employed_STARs"],
            mode="lines",
            line=dict(color=color, width=3, dash="dot"),
            name=f"{label}  Employment",
            yaxis="y2",
        ))

st.plotly_chart(fig4, width="stretch")
st.caption("Solid lines = Median Wage (left axis)  ·  Dotted lines = Employment (right axis)")

# Expandable section displaying raw data for selected counties
with st.expander(" Show raw data for selected counties"):
    for df, label in zip(county_long_dfs, labels):
        st.markdown(f"**{label}**")
        st.dataframe(df.reset_index(drop=True), width="stretch")
