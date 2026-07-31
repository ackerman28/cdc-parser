import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_excel("analysis/Africa_CDC_Merged_v3.xlsx")
df["Report Date"] = pd.to_datetime(df["Report Date"])
FREEZE = pd.Timestamp("2025-01-20")
df["post"] = (df["Report Date"] >= FREEZE).astype(int)
usaid = "USAID share of total ODA gross disbursements received, 2023"

me = df[df["Agent/Syndrome"] == "Measles virus"]

# ---- TABLE: measles reports pre/post + other-disease activity + USAID share ----
mtab = me.groupby(["Country", "post"]).size().unstack(fill_value=0)
mtab.columns = ["measles_pre", "measles_post"]
other_post = df[(df["Agent/Syndrome"] != "Measles virus") & (df["post"] == 1)].groupby("Country").size()
mtab["other_dis_post"] = other_post.reindex(mtab.index).fillna(0).astype(int)
mtab["usaid_share"] = df.groupby("Country")[usaid].first().reindex(mtab.index).round(3)
mtab = mtab.reset_index()

drop8 = mtab[(mtab["measles_pre"] > 0) & (mtab["measles_post"] == 0)].sort_values("measles_pre", ascending=False)
drop8.to_csv("analysis/measles_dropouts_table.csv", index=False)
print("=== Countries that STOPPED reporting measles after the freeze ===")
print(drop8.to_string(index=False))
print("\nNote: 'other_dis_post' shows they kept reporting OTHER diseases — so it's measles-specific.")

# ---- BAR CHART: measles reports before vs after, biggest declines ----
mtab2 = me.groupby(["Country", "post"]).size().unstack(fill_value=0)
mtab2.columns = ["pre", "post"]
mtab2["change"] = mtab2["post"] - mtab2["pre"]
top = mtab2.sort_values("change").head(12).sort_values("pre", ascending=True)

fig, ax = plt.subplots(figsize=(11, 7))
y = np.arange(len(top))
ax.barh(y - 0.2, top["pre"], height=0.4, label="Before freeze", color="#2ca02c")
ax.barh(y + 0.2, top["post"], height=0.4, label="After freeze", color="#d62728")
ax.set_yticks(y); ax.set_yticklabels(top.index)
ax.set_xlabel("Number of measles reports")
ax.set_title("Measles surveillance reports before vs after Jan 2025 freeze\n(12 countries with the largest declines)")
ax.legend(); ax.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig("analysis/fig_measles_dropoff.png", dpi=150, bbox_inches="tight")
print("\nSaved analysis/fig_measles_dropoff.png and measles_dropouts_table.csv")
plt.close()