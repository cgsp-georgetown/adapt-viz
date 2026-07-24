from dashboard_lib import data
from dashboard_lib.paths import COLLEGE_PANEL
import pandas as pd
# national_df, long_df, cbp_df, tradserv_df = load_data()
# grad_df = load_grad_data()

# national_df, long_df, cbp_df, tradserv_df = data.load_data()
# grad_df = data.load_grad_data()

# def load_grad_data():
#     df = pd.read_stata(COLLEGE_PANEL)
#     df2022 = df[df["year"] == 2022].copy()
#     df2022["county_fips"] = df2022["county_fips"].astype("Int64")
#     grads = df2022.groupby("county_fips").apply(
#         lambda g: pd.Series({
#             "pub_fouryear_grads_2022":  g.loc[g["college_label"].str.contains("public",  na=False) & (g["level"] == "4+ years"), "numbergraduates"].sum(),
#             "pub_subba_grads_2022":     g.loc[g["college_label"].str.contains("public",  na=False) & (g["level"] != "4+ years"), "numbergraduates"].sum(),
#             "priv_fouryear_grads_2022": g.loc[g["college_label"].str.contains("private", na=False) & (g["level"] == "4+ years"), "numbergraduates"].sum(),
#             "priv_subba_grads_2022":    g.loc[g["college_label"].str.contains("private", na=False) & (g["level"] != "4+ years"), "numbergraduates"].sum(),
#             "total_fouryear_grads_2022": g.loc[g["level"] == "4+ years", "numbergraduates"].sum(),
#             "total_subba_grads_2022":    g.loc[g["level"] != "4+ years", "numbergraduates"].sum(),
#         })
#     ).reset_index()
#     return grads

def load_grad_data():
    df = pd.read_stata(COLLEGE_PANEL)

    # Filter early to reduce the amount of data processed.
    df2022 = df.loc[
        df["year"].eq(2022),
        ["county_fips", "college_label", "level", "numbergraduates"],
    ].copy()

    df2022["county_fips"] = df2022["county_fips"].astype("Int64")

    # Calculate each condition once.
    is_public = df2022["college_label"].str.contains("public", na=False)
    is_private = df2022["college_label"].str.contains("private", na=False)
    is_fouryear = df2022["level"].eq("4+ years")
    is_subba = df2022["level"].ne("4+ years")

    graduates = df2022["numbergraduates"]

    # Create the six output variables using vectorized masks.
    df2022["pub_fouryear_grads_2022"] = graduates.where(
        is_public & is_fouryear, 0
    )
    df2022["pub_subba_grads_2022"] = graduates.where(
        is_public & is_subba, 0
    )
    df2022["priv_fouryear_grads_2022"] = graduates.where(
        is_private & is_fouryear, 0
    )
    df2022["priv_subba_grads_2022"] = graduates.where(
        is_private & is_subba, 0
    )
    df2022["total_fouryear_grads_2022"] = graduates.where(
        is_fouryear, 0
    )
    df2022["total_subba_grads_2022"] = graduates.where(
        is_subba, 0
    )

    output_columns = [
        "pub_fouryear_grads_2022",
        "pub_subba_grads_2022",
        "priv_fouryear_grads_2022",
        "priv_subba_grads_2022",
        "total_fouryear_grads_2022",
        "total_subba_grads_2022",
    ]

    grads = (
        df2022.groupby("county_fips", as_index=False)[output_columns]
        .sum()
    )

    return grads

initial_grads_df = data.load_grad_data()
optimized_grads_df = load_grad_data()

## check whether the two DataFrames are equal
assert initial_grads_df.equals(optimized_grads_df)
print(initial_grads_df.equals(optimized_grads_df))
