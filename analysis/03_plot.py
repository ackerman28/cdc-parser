import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("analysis/panel_ready.csv")
df["month"] = pd.to_datetime(df["month"])

# Monthly report counts per group
monthly = df.groupby(["month", "treated"]).size().reset_index(name="n_reports")
pivot = monthly.pivot(index="month", columns="treated", values="n_reports").fillna(0)
pivot.columns = ["Low USAID dependence", "High USAID dependence"]

FREEZE = pd.Timestamp("2025-01-20")

fig, ax = plt.subplots(figsize=(11, 6))
ax.plot(pivot.index, pivot["High USAID dependence"], marker="o", label="High USAID dependence (treated)")
ax.plot(pivot.index, pivot["Low USAID dependence"],  marker="o", label="Low USAID dependence")
ax.axvline(FREEZE, color="red", linestyle="--", linewidth=1.5)
ax.text(FREEZE, ax.get_ylim()[1]*0.95, "  Jan 2025 freeze", color="red", va="top")

ax.set_title("Africa CDC surveillance reports per month, by USAID dependence")
ax.set_xlabel("Month")
ax.set_ylabel("Number of outbreak reports")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig("analysis/surveillance_trend.png", dpi=150)
print("Saved analysis/surveillance_trend.png")
plt.show()