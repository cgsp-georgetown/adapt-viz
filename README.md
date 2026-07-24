# ADAPT-Viz dashboard

ADAPT-Viz is a multi-page [Streamlit](https://streamlit.io/) dashboard for exploring county-level economic opportunity in the United States. The main page combines county rankings, maps, workforce and education metrics, industry and occupation tables, and historical trends. The **County Pair Matching** page compares counties with similar starting conditions and different education spending or recovery outcomes.

## Key points

- The dashboard runs locally with Python; Docker is not required.
- Python 3.10 or newer is required.
- `main.py` is the Streamlit entry point.
- Streamlit automatically discovers additional pages in `pages/`.
- Data loading and transformation live in `dashboard_lib/data.py`, `dashboard_lib/main_data.py`, and `dashboard_lib/pair_matching.py`.
- UI components and Plotly figures live in `dashboard_lib/main_views.py`, `dashboard_lib/main_maps.py`, and `dashboard_lib/pair_views.py`.
- Data paths are defined centrally in `dashboard_lib/paths.py`; paths are resolved from the repository root, so the app can be launched from any working directory when the full path to `main.py` is supplied.
- Large, read-only datasets and figures are cached with Streamlit. The first load can take longer than later reruns.
- County geometry is loaded from the local `data/geojson-counties-fips.json` file; the map does not need to download geometry at runtime.

## Project structure

```text
adapt-viz/
|-- main.py                         # Main Streamlit entry point
|-- dashboard_lib/
|   |-- data.py                     # Source-data readers
|   |-- paths.py                    # Central data-path definitions
|   |-- main_data.py                # Main-page preparation and metrics
|   |-- main_views.py               # Main-page Streamlit components/charts
|   |-- main_maps.py                # Plotly county maps
|   |-- pair_matching.py            # County-pair data and matching logic
|   `-- pair_views.py               # County-pair page components/charts
|-- pages/
|   `-- county_pair_matching.py     # Additional Streamlit page
|-- data/                           # Local dashboard datasets
|-- scripts/                        # Data preparation scripts
|-- tests/                          # Pytest test suite
|-- requirements.txt               # Runtime dependencies
`-- pyproject.toml                  # Package metadata and Python version
```

## Run locally without Docker

### 1. Get the repository and enter it

If the repository is not already on your machine:

```bash
git clone <repository-url>
cd adapt-viz
```

Run all remaining commands from the repository root (the directory containing `main.py`).

### 2. Create a virtual environment

Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If PowerShell blocks activation, allow locally created scripts for the current terminal session and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The runtime dependencies are Streamlit, pandas, NumPy, and Plotly. Installing with `python -m pip` ensures packages go into the active virtual environment.

### 4. Confirm the required data is present

The repository's `data/` directory must contain at least these runtime files:

```text
county_all_vars_wide.dta
county_all_vars_long.dta
county_all_vars_long.csv
cbp_county_2016.csv
cbp_county_2016_all_tradserv_emp.csv
county_panel_90001122.dta
county_similarity_matrix.dta
2022_industry_county_summary.csv.gz
2022_occupation_county_summary.csv.gz
geojson-counties-fips.json
```

The main page uses the Stata wide/long files, employment files, graduate panel, 2022 summaries, and local GeoJSON. The County Pair Matching page also uses the long CSV and similarity matrix. A missing file will cause a `FileNotFoundError` that identifies the expected path.

If the two compressed 2022 summary files need to be rebuilt and `data/2022_occind.dta` is available, run:

```bash
python scripts/build_2022_industry_summary.py
```

### 5. Start Streamlit

```bash
python -m streamlit run main.py
```

Streamlit normally opens the dashboard automatically at `http://localhost:8501`. If it does not, open that address in a browser. Use the sidebar navigation to switch between the main dashboard and **County Pair Matching**.

Stop the server with `Ctrl+C`. On later runs, reactivate the virtual environment and repeat only the Streamlit command.

## Run tests

Pytest is a development dependency and is not currently included in `requirements.txt`:

```bash
python -m pip install pytest
python -m pytest -q
```

## Add a visual element to an existing page

Keep calculations separate from rendering so the component can be tested and reused. For example, to add a chart to the main page:

1. Identify the source columns and add any reusable calculation or filtering function to `dashboard_lib/main_data.py`. Raw file readers belong in `dashboard_lib/data.py`, and any new path constant belongs in `dashboard_lib/paths.py`.
2. Add a focused render function to `dashboard_lib/main_views.py`. Give every interactive widget or Plotly chart a stable, unique Streamlit `key`.
3. Call the new render function from `render_dashboard()` in `dashboard_lib/main_views.py` at the desired location.
4. Pass prepared data into the view instead of reading or transforming a full dataset inside the render function.
5. Add unit tests for calculations or figure/table preparation in `tests/`.
6. Run `python -m pytest -q`, then launch Streamlit and verify the visual at narrow and wide browser sizes.

Minimal pattern:

```python
# dashboard_lib/main_views.py
import plotly.express as px
import streamlit as st


def render_example_chart(county_long_df):
    figure = px.line(
        county_long_df.sort_values("year"),
        x="year",
        y="star_median",
        title="Median non-college wage",
    )
    st.plotly_chart(
        figure,
        use_container_width=True,
        key="example_median_wage_chart",
    )
```

Then call it from the page composition function:

```python
# Inside render_dashboard(...) in dashboard_lib/main_views.py
render_example_chart(county_data["county_long_df"])
```

For an element on the County Pair Matching page, use the same pattern in `dashboard_lib/pair_views.py` and call it from `pages/county_pair_matching.py` or from an existing pair-page composition function.

## Create a new page

Streamlit treats each Python file in `pages/` as a page. To add one while keeping the project structure consistent:

1. Put page-specific data preparation in a new module such as `dashboard_lib/regional_data.py`.
2. Put charts and Streamlit UI functions in a new module such as `dashboard_lib/regional_views.py`.
3. Create `pages/regional_overview.py` as the thin page entry point.
4. Set the page configuration before calling any other Streamlit command.
5. Load data through cached functions, render the page, and call `main()`.
6. Add tests for non-UI calculations, run the test suite, and start the dashboard to confirm the new page appears in navigation.

Example page entry point:

```python
# pages/regional_overview.py
import streamlit as st

from dashboard_lib.regional_data import load_regional_data
from dashboard_lib.regional_views import render_regional_overview


st.set_page_config(page_title="Regional Overview", layout="wide")


def main():
    regional_data = load_regional_data()
    render_regional_overview(regional_data)


main()
```

Use `@st.cache_data` for functions that return serializable data such as DataFrames, and `@st.cache_resource` only for shared resource objects that should be reused across reruns. Treat objects returned by `@st.cache_resource` as immutable, or copy them before modification.

## Data and development notes

- Preserve county FIPS values as five-character strings when leading zeroes matter (for example, `"01001"`).
- Prefer compact pre-aggregated dashboard inputs over repeatedly processing `2022_occind.dta` during page rendering.
- Do not mutate cached shared DataFrames in place. Select or copy the required rows first.
- Keep network access out of page rendering when a stable local asset is available.
- When adding a dataset, update `dashboard_lib/paths.py`, add a loader in the appropriate data module, document the file here, and add validation tests for identifiers and required columns.
