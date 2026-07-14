import pandas as pd
import pytest

from dashboard_lib.pair_matching import build_pairs, classify_recovery


@pytest.mark.parametrize(
    ("employment_growth", "income_growth", "expected"),
    [
        (0.1, 0.1, "both"),
        (0.1, 0.0, "emp"),
        (0.0, 0.1, "inc"),
        (0.0, 0.0, "loss"),
        (-0.1, -0.1, "loss"),
    ],
)
def test_classify_recovery(employment_growth, income_growth, expected):
    row = {
        "d_pct_star_emp_2000_2022": employment_growth,
        "d_star_med_pct_2000_2022": income_growth,
    }

    assert classify_recovery(row) == expected


def make_pool():
    return pd.DataFrame(
        [
            {
                "countyid": 1001,
                "county_name": "High County",
                "statefips": 1,
                "state": "AL",
                "workagepop_1990": 50_000,
                "ppupil_deflate1990": 1_000,
                "d_star_med_pct_2000_2022": 0.30,
                "d_pct_star_emp_2000_2022": 0.25,
                "d_m_usdev82000_2011": 1.2,
                "recovery": "both",
                "RUCC_2013": 2,
                "mfg_empsh": 0.20,
                "ag_empsh": 0.05,
                "gov_empsh": 0.10,
                "college_lf_share_1990": 0.15,
            },
            {
                "countyid": 1003,
                "county_name": "Low County",
                "statefips": 1,
                "state": "AL",
                "workagepop_1990": 55_000,
                "ppupil_deflate1990": 600,
                "d_star_med_pct_2000_2022": 0.10,
                "d_pct_star_emp_2000_2022": 0.05,
                "d_m_usdev82000_2011": 1.0,
                "recovery": "both",
                "RUCC_2013": 2,
                "mfg_empsh": 0.21,
                "ag_empsh": 0.06,
                "gov_empsh": 0.11,
                "college_lf_share_1990": 0.16,
            },
            {
                "countyid": 2001,
                "county_name": "Other State County",
                "statefips": 2,
                "state": "AK",
                "workagepop_1990": 52_000,
                "ppupil_deflate1990": 500,
                "d_star_med_pct_2000_2022": 0.00,
                "d_pct_star_emp_2000_2022": 0.00,
                "d_m_usdev82000_2011": 1.1,
                "recovery": "loss",
                "RUCC_2013": 2,
                "mfg_empsh": 0.20,
                "ag_empsh": 0.05,
                "gov_empsh": 0.10,
                "college_lf_share_1990": 0.15,
            },
        ]
    )


def test_build_pairs_preserves_matching_and_scoring_behavior():
    pairs = build_pairs(
        make_pool(),
        min_shock=1.0,
        min_ppupil_diff=300,
        recovery_filter=["both", "emp", "inc", "loss"],
        sim_pct=100,
        require_rucc=True,
        pop_range=(40_000, 60_000),
    )

    assert len(pairs) == 1
    pair = pairs.iloc[0]
    assert pair["county_name_H"] == "High County"
    assert pair["county_name_L"] == "Low County"
    assert pair["d_ppupil"] == 400
    assert pair["d_wage_growth"] == pytest.approx(0.20)
    assert pair["d_emp_growth"] == pytest.approx(0.20)
    assert pair["pair_score"] == pytest.approx(7.8)


def test_build_pairs_applies_recovery_filter():
    pairs = build_pairs(
        make_pool(),
        min_shock=1.0,
        min_ppupil_diff=300,
        recovery_filter=["loss"],
        sim_pct=100,
        require_rucc=True,
    )

    assert pairs.empty


def test_build_pairs_applies_population_filter():
    pairs = build_pairs(
        make_pool(),
        min_shock=1.0,
        min_ppupil_diff=300,
        recovery_filter=["both", "emp", "inc", "loss"],
        sim_pct=100,
        require_rucc=True,
        pop_range=(51_000, 60_000),
    )

    assert pairs.empty
