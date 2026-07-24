import pandas as pd

# Load data
df = pd.read_csv("erscountytypology2025edition.csv")


# -------------------------------------------------------
# 1. Define attributes to keep
# -------------------------------------------------------
attributes_keep = [
    "Industry_Dependence_2025",
    "Low_PostSecondary_Ed_2025",
    "Retirement_Destination_2025"
]

# Keep only these attributes
df_filtered = df[df["Attribute"].isin(attributes_keep)]

# -------------------------------------------------------
# 2. Pivot to county-level feature matrix
# -------------------------------------------------------
county_features = (
    df_filtered.pivot_table(
        index=["FIPStxt", "State", "County_Name"],
        columns="Attribute",
        values="Value",
        aggfunc="first"
    )
    .reset_index()
)

# -------------------------------------------------------
# 3. Add Metro2023 as a feature
# -------------------------------------------------------
metro = df[["FIPStxt", "Metro2023"]].drop_duplicates()
county_features = county_features.merge(metro, on="FIPStxt", how="left")

# -------------------------------------------------------
# 4. Define feature columns
# -------------------------------------------------------
feature_cols = attributes_keep + ["Metro2023"]

# Ensure missing values become 0 (sometimes occurs in pivot)
county_features[attributes_keep] = county_features[attributes_keep].fillna(0)

# -------------------------------------------------------
# 5. Create bucket IDs from feature combinations
# -------------------------------------------------------
county_features["bucket_id"] = (
    county_features[feature_cols]
    .astype(int)
    .astype(str)
    .agg("_".join, axis=1)
)

# -------------------------------------------------------
# 6. Count counties in each bucket
# -------------------------------------------------------
bucket_counts = (
    county_features
    .groupby("bucket_id")
    .size()
    .reset_index(name="county_count")
    .sort_values("county_count", ascending=False)
)

# -------------------------------------------------------
# 7. Summary statistics
# -------------------------------------------------------
total_buckets = len(bucket_counts)
multi_county_buckets = (bucket_counts["county_count"] > 1).sum()
singleton_buckets = (bucket_counts["county_count"] == 1).sum()

print("Total unique buckets:", total_buckets)
print("Buckets with >1 county:", multi_county_buckets)
print("Buckets with only 1 county:", singleton_buckets)

# -------------------------------------------------------
# 8. Distribution of bucket sizes
# -------------------------------------------------------
bucket_distribution = (
    bucket_counts["county_count"]
    .value_counts()
    .sort_index()
)

print("\nDistribution of counties per bucket:")
print(bucket_distribution)

# -------------------------------------------------------
# 9. Attach bucket info back to counties
# -------------------------------------------------------
county_buckets = county_features.merge(bucket_counts, on="bucket_id")

# Save outputs
bucket_counts.to_csv("bucket_counts.csv", index=False)
county_buckets.to_csv("county_bucket_assignments.csv", index=False)