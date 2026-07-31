import pandas as pd

# Load the merged dataset
df = pd.read_excel("analysis/Africa_CDC_Merged.xlsx")

# Confirm it loaded: how many rows and columns?
print("Shape:", df.shape)
print("Rows:", df.shape[0], "| Columns:", df.shape[1])

# --- Step 4: look inside the data ---

# What are all the columns called?
print("\n=== COLUMNS ===")
for i, col in enumerate(df.columns):
    print(i, col)

# What date range does the surveillance data cover?
df["Report Date"] = pd.to_datetime(df["Report Date"], errors="coerce")
print("\n=== DATE RANGE ===")
print("Earliest:", df["Report Date"].min())
print("Latest:  ", df["Report Date"].max())

# How many countries, and which ones?
print("\n=== COUNTRIES ===")
print("Number of countries:", df["Country"].nunique())
print(sorted(df["Country"].unique()))
# --- Step 5: look at the disease/outcome data ---

# Which diseases (agents/syndromes) are in the data, and how often?
print("\n=== DISEASES (Agent/Syndrome) ===")
print("Number of distinct diseases:", df["Agent/Syndrome"].nunique())
print(df["Agent/Syndrome"].value_counts())

# Show a few real rows, just the key columns, so we see actual values
print("\n=== SAMPLE ROWS (key columns) ===")
key_cols = ["Report Date", "Country", "Agent/Syndrome",
            "new_confirmed", "new_deaths",
            "USAID share of total ODA gross disbursements received, 2023"]
print(df[key_cols].head(10).to_string())