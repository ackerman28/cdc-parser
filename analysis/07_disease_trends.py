import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("analysis/Africa_CDC_Merged_v3.xlsx")
df["Report Date"] = pd.to_datetime(df["Report Date"])
df["month"] = df["Report Date"].dt.to_period("M").dt.to_timestamp()
FREEZE = pd.Timestamp("2025-01-20")

# Focus on the diseases that dominate the data
top_diseases = ["Vibrio cholerae", "Mpox virus", "Measles virus"]

# Outcome = number of COUNTRIES reporting each disease per month
# (Divya's "surveillance intensity" idea: how many countries are actively reporting)
sub = df[df["Agent/Syndrome"].isin(top_diseases)]
counts = (sub.groupby(["month", "Agent/Syndrome"])["Country"]
             .nunique().reset_index(name="n_countries"))
pivot = counts.pivot(index="month", columns="Agent/Syndrome",
                     values="n_countries").fillna(0)

fig, ax = plt.subplots(figsize=(12, 6))
for d in top_diseases:
    if d in pivot.columns:
        ax.plot(pivot.index, pivot[d], marker="o", label=d)
ax.axvline(FREEZE, color="red", linestyle="--", linewidth=1.5)
ax.text(FREEZE, ax.get_ylim()[1]*0.97, "  Jan 2025 freeze", color="red", va="top")

ax.set_title("Number of countries reporting each disease per month (through Jul 2026)")
ax.set_xlabel("Month")
ax.set_ylabel("Countries reporting")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("analysis/disease_trends_through_july2026.png", dpi=150)
print("Saved analysis/disease_trends_through_july2026.png")
plt.show()