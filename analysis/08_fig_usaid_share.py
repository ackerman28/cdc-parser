import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_excel("analysis/Africa_CDC_Merged_v3.xlsx")
df["Report Date"] = pd.to_datetime(df["Report Date"])
df["month"] = df["Report Date"].dt.to_period("M").dt.to_timestamp()
FREEZE = pd.Timestamp("2025-01-20")

# Split countries into high vs low USAID share (median cutoff)
usaid = "USAID share of total ODA gross disbursements received, 2023"
cu = df.groupby("Country")[usaid].first()
cutoff = cu.median()
high = set(cu[cu >= cutoff].index)
df["grp"] = np.where(df["Country"].isin(high), "High", "Low")

top = ["Vibrio cholerae", "Mpox virus", "Measles virus"]
colors = {"Vibrio cholerae": "#1f77b4", "Mpox virus": "#ff7f0e", "Measles virus": "#2ca02c"}

def make_figure(grp, title, outfile):
    sub = df[(df["grp"] == grp) & (df["Agent/Syndrome"].isin(top))]
    fig, ax = plt.subplots(figsize=(12, 6))
    for d in top:
        s = sub[sub["Agent/Syndrome"] == d].groupby("month")["Country"].nunique()
        ax.plot(s.index, s.values, marker="o", label=d, color=colors[d])
    ax.axvline(FREEZE, color="red", ls="--", lw=1.5)
    ax.text(FREEZE, ax.get_ylim()[1] * 0.97, "  Jan 2025 freeze",
            color="red", va="top", fontsize=9)
    ax.set_title(title)
    ax.set_xlabel("Month")
    ax.set_ylabel("Countries reporting")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    print("Saved", outfile)
    plt.close()

make_figure("High",
            f"Countries reporting each disease per month — High USAID share ({len(high)} countries)",
            "analysis/fig_usaid_share_HIGH.png")

make_figure("Low",
            f"Countries reporting each disease per month — Low USAID share ({41 - len(high)} countries)",
            "analysis/fig_usaid_share_LOW.png")