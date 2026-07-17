import pandas as pd
import pytest

from scripts.build_2022_industry_summary import (
    aggregate_chunk,
    normalize_county_fips,
    validate_summary,
)
from dashboard_lib.main_views import prepare_industry_table


def test_normalize_county_fips():
    values = pd.Series([6037, "01001", 36061.0])

    assert normalize_county_fips(values).tolist() == ["06037", "01001", "36061"]


def test_aggregate_chunk_collapses_occupations():
    source = pd.DataFrame(
        {
            "fips_concat": ["06037", "06037", "06037", "01001"],
            "ind1990": ["Hospitals", "Hospitals", "Construction", "Hospitals"],
            "employed_workers": [100.0, 50.0, 80.0, 20.0],
            "employed_STARs": [40.0, 10.0, 60.0, 5.0],
        }
    )

    result = aggregate_chunk(source)
    la_hospitals = result[
        result["county_fips"].eq("06037") & result["industry"].eq("Hospitals")
    ].iloc[0]

    assert la_hospitals["employed_workers"] == 150.0
    assert la_hospitals["employed_noncollege"] == 50.0
    assert len(result) == 3


def test_validate_summary_rejects_duplicate_industries():
    summary = pd.DataFrame(
        {
            "county_fips": ["06037", "06037"],
            "industry": ["Hospitals", "Hospitals"],
            "employed_workers": [100.0, 50.0],
            "employed_noncollege": [40.0, 10.0],
        }
    )

    with pytest.raises(ValueError, match="duplicate"):
        validate_summary(summary)


def test_validate_summary_rejects_noncollege_above_total():
    summary = pd.DataFrame(
        {
            "county_fips": ["06037"],
            "industry": ["Hospitals"],
            "employed_workers": [100.0],
            "employed_noncollege": [101.0],
        }
    )

    with pytest.raises(ValueError, match="exceeds"):
        validate_summary(summary)


def test_prepare_industry_table_calculates_share_and_sorts():
    county_data = pd.DataFrame(
        {
            "county_fips": ["06037", "06037", "06037"],
            "industry": ["Smaller", "Larger", "Zero"],
            "employed_workers": [100.0, 400.0, 0.0],
            "employed_noncollege": [25.0, 240.0, 0.0],
        }
    )

    result = prepare_industry_table(county_data)

    assert result.columns.tolist() == [
        "Industry",
        "Employment",
        "Non-College Workers",
        "Non-College Share (%)",
    ]
    assert result["Industry"].tolist() == ["Larger", "Smaller"]
    assert result["Non-College Share (%)"].tolist() == [60.0, 25.0]


def test_prepare_industry_table_handles_empty_input():
    source = pd.DataFrame(
        columns=[
            "county_fips",
            "industry",
            "employed_workers",
            "employed_noncollege",
        ]
    )

    result = prepare_industry_table(source)

    assert result.empty
    assert result.columns.tolist() == [
        "Industry",
        "Employment",
        "Non-College Workers",
        "Non-College Share (%)",
    ]
