import pandas as pd

df = pd.read_excel("analysis/Africa_CDC_Merged.xlsx")
df["Report Date"] = pd.to_datetime(df["Report Date"], errors="coerce")

# --- 1. Time: before vs after the Jan 2025 funding freeze ---
FREEZE = pd.Timestamp("2025-01-20")
df["post"] = (df["Report Date"] >= FREEZE).astype(int)
df["month"] = df["Report Date"].dt.to_period("M").dt.to_timestamp()

# --- 2. Treatment: high vs low USAID dependence (pre-cut, fixed per country) ---
usaid = "USAID share of total ODA gross disbursements received, 2023"
# median split across the 41 countries
country_usaid = df.groupby("Country")[usaid].first()
cutoff = country_usaid.median()
high_countries = country_usaid[country_usaid >= cutoff].index
df["treated"] = df["Country"].isin(high_countries).astype(int)
print(f"USAID-share median cutoff: {cutoff:.3f}")
print(f"High-dependence (treated) countries: {len(high_countries)} | Low: {41-len(high_countries)}")

# --- 3. Outcome: monthly surveillance activity (reports = outbreak-monitoring intensity) ---
monthly = (df.groupby(["month", "treated"])
             .size().reset_index(name="n_reports"))

pivot = monthly.pivot(index="month", columns="treated", values="n_reports").fillna(0)
pivot.columns = ["Low_USAID", "High_USAID"]
print("\n=== Monthly report counts, by group ===")
print(pivot.to_string())

# Save the analysis-ready dataframe for later steps
df.to_csv("analysis/panel_ready.csv", index=False)
print("\nSaved analysis/panel_ready.csv")