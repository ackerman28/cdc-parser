import pandas as pd
import numpy as np

df = pd.read_csv("analysis/panel_ready.csv")
df["month"] = pd.to_datetime(df["month"])
FREEZE = pd.Timestamp("2025-01-20")
df["post"] = (df["month"] >= FREEZE).astype(int)
usaid = "USAID share of total ODA gross disbursements received, 2023"
oda_pc = "ODA gross disbursements received per person, 2023 (USD)"
oda_tot = "ODA gross disbursements received, 2023 (USD millions)"

# ---- 1. Save the per-country pre/post table as CSV (for the notebook) ----
tab = (df.groupby(["Country", "treated", "post"]).size()
         .unstack("post", fill_value=0))
tab.columns = ["pre_freeze", "post_freeze"]
tab["total"] = tab["pre_freeze"] + tab["post_freeze"]
pre = tab["pre_freeze"].astype(float)
post = tab["post_freeze"].astype(float)
tab["pct_change"] = np.where(pre > 0, (post - pre) / pre * 100, np.nan).round(1)
tab = tab.reset_index().sort_values("total", ascending=False)
tab.to_csv("analysis/reports_by_country.csv", index=False)
print("Saved analysis/reports_by_country.csv")

# ---- 2. Divya point 6: average ODA (per country, then summarized) ----
per_country = df.groupby("Country").agg(
    usaid_share=(usaid, "first"),
    oda_per_capita=(oda_pc, "first"),
    oda_total_musd=(oda_tot, "first"),
).reset_index()
print("\n=== AVERAGE ODA across the 41 countries ===")
print(f"Mean USAID share of ODA : {per_country['usaid_share'].mean():.3f}")
print(f"Mean ODA per person     : ${per_country['oda_per_capita'].mean():.1f}")
print(f"Mean total ODA          : ${per_country['oda_total_musd'].mean():.0f}m")

# ---- 3. Divya point 6: frequency of diseases across countries ----
dis = df.groupby("Agent/Syndrome").agg(
    n_reports=("Country", "size"),
    n_countries=("Country", "nunique"),
).reset_index().sort_values("n_reports", ascending=False)
dis.to_csv("analysis/disease_frequency.csv", index=False)
print("\n=== DISEASE FREQUENCY (top 10) ===")
print(dis.head(10).to_string(index=False))
print("\nSaved analysis/disease_frequency.csv")