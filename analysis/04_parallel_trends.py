import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("analysis/panel_ready.csv")
df["month"] = pd.to_datetime(df["month"])
FREEZE = pd.Timestamp("2025-01-20")

# Normalize each group to its own pre-freeze average, so we compare *trends* not levels
monthly = df.groupby(["month", "treated"]).size().reset_index(name="n")
pivot = monthly.pivot(index="month", columns="treated", values="n").fillna(0)
pivot.columns = ["Low", "High"]

pre = pivot[pivot.index < FREEZE]
norm = pivot / pre.mean()   # 1.0 = each group's own pre-freeze average

fig, ax = plt.subplots(figsize=(11, 6))
ax.plot(norm.index, norm["High"], marker="o", label="High USAID dependence")
ax.plot(norm.index, norm["Low"],  marker="o", label="Low USAID dependence")
ax.axvline(FREEZE, color="red", linestyle="--")
ax.axhline(1.0, color="gray", linewidth=0.8)
ax.set_title("Surveillance reports relative to each group's pre-freeze average")
ax.set_ylabel("Reports ÷ own pre-freeze mean (1.0 = baseline)")
ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("analysis/parallel_trends.png", dpi=150)
print("Saved analysis/parallel_trends.png")

# Numeric check: correlation of the two groups' monthly counts in the PRE period
corr = pre["Low"].corr(pre["High"])
print(f"\nPre-freeze correlation between groups: {corr:.3f}")
print("(closer to 1.0 = they moved together = parallel-trends looks plausible)")
plt.show()