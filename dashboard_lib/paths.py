## Paths for data sources 
## need to work on this because many data sources are duplicated. Need to have a single source of truth
## Need to remove all strings from data sources and create a keys table that maps the keys to the data sources. This will make it lighter.

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" 

COUNTIES_GEOJSON = DATA_DIR / "geojson-counties-fips.json"
COUNTY_WIDE = DATA_DIR / "county_all_vars_wide.dta"
COUNTY_LONG_DTA = DATA_DIR / "county_all_vars_long.dta"
COUNTY_LONG_CSV = DATA_DIR / "county_all_vars_long.csv"
COUNTY_INDEX = DATA_DIR / "county_all_vars_index.dta"
COUNTY_POST_INDEX = DATA_DIR / "county_all_vars_post_index.csv"
CBP_COUNTY_2016 = DATA_DIR / "cbp_county_2016.csv"
TRADSERV_2016 = DATA_DIR / "cbp_county_2016_all_tradserv_emp.csv"
COLLEGE_PANEL = DATA_DIR / "county_panel_90001122.dta"
CZONE_COUNTY = DATA_DIR / "czone_county.csv"
SIMILARITY_MATRIX = DATA_DIR / "county_similarity_matrix.dta"
