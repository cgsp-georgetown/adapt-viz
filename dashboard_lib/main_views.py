"""Streamlit views for the main county dashboard."""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from .main_data import get_county_options, get_state_options, rank_within_population_quintile
from .main_maps import (
    TRADE_METRICS,
    WAGE_METRICS,
    apply_zoom,
    build_national_map,
    build_trade_map,
    build_wage_map,
    county_zoom_settings,
    hide_ak_hi,
)


DASHBOARD_STYLE = """
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto, sans-serif:wght@100&display=swap');

            html, body, [class*="css"]  {
            font-family: 'Roboto, sans-serif', sans-serif;
            }
            </style>
            """


def apply_dashboard_style():
    st.markdown(DASHBOARD_STYLE, unsafe_allow_html=True)


def render_county_selector(national_df):
    sorted_states, default_state_index = get_state_options(national_df)
    st.sidebar.write("### Select County")
    state = st.sidebar.selectbox("State", sorted_states, index=default_state_index)
    state_df, sorted_counties, default_county_index = get_county_options(
        national_df, state
    )
    county = st.sidebar.selectbox(
        "County", sorted_counties, index=default_county_index
    )
    return state_df, county


def render_map_sections(wide_df, long_df, county, county_id):
    st.title("American Dream Achievability Progress Tracker")
    st.markdown('<p style="font-size:18px;">See the local geography of global opportunity. For local policymakers, employers, and citizens.</p>', unsafe_allow_html=True)

    _national_fig = hide_ak_hi(build_national_map(wide_df))
    _tradserv_fig = hide_ak_hi(
        build_trade_map(wide_df, "tradserv_exp_emp_2017_2022", "Blues")
    )
    _zoom_geo = county_zoom_settings(county_id)
    apply_zoom(_national_fig, _zoom_geo)
    apply_zoom(_tradserv_fig, _zoom_geo)

    st.subheader("Manufacturing Trade Shocks")
    st.caption("Estimated job flows from changes in manufacturing import competition and export growth. Use the dropdown to filter by population quartile.")
    _trade_label = st.selectbox("Select metric", list(TRADE_METRICS.keys()), key="trade_map_metric")
    _trade_col, _trade_cs, _ = TRADE_METRICS[_trade_label]
    _trade_fig = apply_zoom(
        hide_ak_hi(build_trade_map(wide_df, _trade_col, _trade_cs)),
        _zoom_geo,
    )
    st.plotly_chart(_trade_fig, use_container_width=True, key="trade_map")

    st.subheader("American Dream Potential Quintile by County")
    st.caption("Calculated by workforce investment and exposure to global trade. Compared to counties with similar population.")

    # Rankings within population quintile
    _county_row  = wide_df[wide_df["countyid"] == county_id]
    _county_qpop5 = _county_row["qpop5"].iloc[0] if len(_county_row) > 0 else None

    def _q5_rank(col, higher_is_better=True):
        return rank_within_population_quintile(
            wide_df,
            county_id,
            _county_qpop5,
            col,
            higher_is_better,
        )

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


def render_county_overview(county, county_data, wide_df, county_id, stats):
    _county_row = wide_df[wide_df["countyid"] == county_id]
    _county_qpop5 = _county_row["qpop5"].iloc[0] if len(_county_row) > 0 else None

    def _q5_rank(col, higher_is_better=True):
        return rank_within_population_quintile(
            wide_df,
            county_id,
            _county_qpop5,
            col,
            higher_is_better,
        )

    county_cbp_df = county_data["county_cbp_df"]
    tradserv_emp = county_data["tradserv_emp"]
    tradserv_pct = county_data["tradserv_pct"]
    mfg_emp_2016 = county_data["mfg_emp_2016"]
    mfg_pct_2016 = county_data["mfg_pct_2016"]
    total_jobs_2022 = county_data["total_jobs_2022"]
    college_jobs_2022 = county_data["college_jobs_2022"]
    noncollege_jobs_2022 = county_data["noncollege_jobs_2022"]
    pub_fouryear_grads_2022 = county_data["pub_fouryear_grads_2022"]
    pub_subba_grads_2022 = county_data["pub_subba_grads_2022"]
    priv_fouryear_grads_2022 = county_data["priv_fouryear_grads_2022"]
    priv_subba_grads_2022 = county_data["priv_subba_grads_2022"]

    star_wage = stats["star_wage"]
    all_wage = stats["college_wage"]
    star_emp = stats["star_emp"]
    college_emp = stats["college_emp"]
    pct_educ2022 = stats["pct_educ2022"]
    ppupil_educ2022 = stats["ppupil_educ2022"]
    job_loss = stats["job_loss"]
    job_gain = stats["job_gain"]
    pct_job_loss = stats["pct_job_loss"]
    pct_job_gain = stats["pct_job_gain"]
    mfgemp_loss = stats["mfgemp_loss"]
    serv_exp_job = stats["serv_exp_job"]
    pct_serv_exp_job = stats["pct_serv_exp_job"]


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


def render_wage_map(long_df, zoom_geo):
    st.subheader("Wages & Employment")
    st.caption("Values normalized to percentile rank within each population size group. Darker blue = higher relative value. Use the dropdown to filter by population quartile.")
    _wage_label = st.selectbox("Select metric", list(WAGE_METRICS.keys()), key="wage_map_metric")
    _wage_col, _ = WAGE_METRICS[_wage_label]
    _wage_fig = apply_zoom(hide_ak_hi(build_wage_map(long_df, _wage_col)), zoom_geo)
    st.plotly_chart(_wage_fig, use_container_width=True, key="wage_map")


def prepare_industry_table(county_industry_df):
    """Prepare the selected county's 2022 industry estimates for display."""
    display_columns = [
        "Industry",
        "Employment",
        "Non-College Workers",
        "Non-College Share (%)",
    ]
    if county_industry_df.empty:
        return pd.DataFrame(columns=display_columns)

    industry_table = county_industry_df[
        ["industry", "employed_workers", "employed_noncollege"]
    ].copy()
    industry_table["employed_workers"] = pd.to_numeric(
        industry_table["employed_workers"], errors="coerce"
    )
    industry_table["employed_noncollege"] = pd.to_numeric(
        industry_table["employed_noncollege"], errors="coerce"
    )
    industry_table = industry_table[
        industry_table["employed_workers"].notna()
        & industry_table["employed_workers"].gt(0)
    ].copy()
    industry_table["noncollege_share"] = (
        industry_table["employed_noncollege"]
        / industry_table["employed_workers"]
        * 100
    )
    industry_table = industry_table.sort_values(
        "employed_workers", ascending=False, kind="stable"
    ).rename(
        columns={
            "industry": "Industry",
            "employed_workers": "Employment",
            "employed_noncollege": "Non-College Workers",
            "noncollege_share": "Non-College Share (%)",
        }
    )
    return industry_table[display_columns].reset_index(drop=True)


def render_industry_table(county_industry_df):
    ### INDUSTRY TABLE
    st.subheader("Industries by Employment")
    industry_table = prepare_industry_table(county_industry_df)
    if industry_table.empty:
        st.info("No 2022 industry employment data is available for this county.")
        return

    st.dataframe(
        industry_table.style.format(
            {
                "Employment": "{:,.0f}",
                "Non-College Workers": "{:,.0f}",
                "Non-College Share (%)": "{:.1f}%",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "2022 estimated employed workers by industry. Non-college workers "
        "include workers without a four-year college degree. Values are "
        "survey-weighted estimates and may not sum exactly due to rounding."
    )


def render_occupation_table(county_id):
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


def render_industry_division(county_cbp_df):
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


def render_trend_charts(county_long_df):
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


def render_dashboard(wide_df, long_df, county, county_data, stats):
    county_id = county_data["county_id"]
    county_long_df = county_data["county_long_df"]
    zoom_geo = county_zoom_settings(county_id)

    render_map_sections(wide_df, long_df, county, county_id)
    render_county_overview(county, county_data, wide_df, county_id, stats)
    render_wage_map(long_df, zoom_geo)
    render_industry_table(county_data["county_industry_df"])
    render_occupation_table(county_id)
    render_industry_division(county_data["county_cbp_df"])
    render_trend_charts(county_long_df)
