### Dashboard 

Project structure:

Industry standard for streamlit dashboard structure:

`dashboard_lib` : contains reusable scripts
`data` : contains all data source files
`pages` : dashboard's different pages

Current to-do: 
1. Data sources are duplicated, need to find keep only necessary data source and keep each column types fixed .dta or .parquet format
2. Remove all strings identifiers from long files (county names, percentile names), and create a seprate small unique cross walk files and connect them via identifiers so dashboard do not load all heavy stuff !!!
3. Remove all internet fetching (for county maps) process 
4. Plotly maps takes up quite time and each time changing state reloads all data again, need to load whole US once and then zoom specific state when user changes.
5. Remove data transformations from `main.py` to `metrics.py` so future adding visualizations with different values will be easier to implement.