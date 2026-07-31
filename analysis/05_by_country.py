import pandas as pd

df = pd.read_csv("analysis/panel_ready.csv")
df["month"] = pd.to_datetime(df["month"])
FREEZE = pd.Timestamp("2025-01-20")
df["post"] = (df["month"] >= FREEZE).astype(int)

# Reports per country, before vs after the freeze
tab = (df.groupby(["Country", "treated", "post"])
         .size().unstack("post", fill_value=0))
tab.columns = ["pre", "post"]
tab["total"] = tab["pre"] + tab["post"]
tab["pct_change"] = ((tab["post"] - tab["pre"]) / tab["pre"] * 100).round(0)
tab = tab.reset_index().sort_values(["treated", "total"], ascending=[True, False])

for grp, label in [(1, "HIGH USAID dependence (treated)"), (0, "LOW USAID dependence")]:
    sub = tab[tab["treated"] == grp]
    print(f"\n=== {label} ===")
    print(sub[["Country", "pre", "post", "total", "pct_change"]].to_string(index=False))
    top3 = sub.nlargest(3, "total")["total"].sum()
    print(f"Top 3 countries = {top3} of {sub['total'].sum()} reports "
          f"({top3/sub['total'].sum()*100:.0f}% of the group)")