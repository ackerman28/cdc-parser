import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_excel("analysis/Africa_CDC_Merged_v3.xlsx")
usaid = "USAID share of total ODA gross disbursements received, 2023"

g = df.groupby("Country").agg(
    pop=("pop_2023", "first"),
    oda_pc=("oda_per_capita_calc", "first"),
    usaid=(usaid, "first"),
    n_reports=("Agent/Syndrome", "size")).reset_index()

fig, ax = plt.subplots(figsize=(13, 8))
x = np.log10(g["pop"]); y = g["oda_pc"]
sizes = g["n_reports"] * 3 + 20
sc = ax.scatter(x, y, s=sizes, alpha=0.6, c=g["usaid"], cmap="YlOrRd", edgecolors="gray")
plt.colorbar(sc, label="USAID share of ODA")

notable = ["Cabo Verde", "Comoros", "South Sudan", "Somalia", "Nigeria",
           "Ethiopia", "Angola", "Central African Republic"]
for _, r in g.iterrows():
    if r["Country"] in notable:
        ax.annotate(r["Country"], (np.log10(r["pop"]), r["oda_pc"]),
                    fontsize=9, xytext=(5, 5), textcoords="offset points")

cv = g[g["Country"] == "Cabo Verde"]
ax.scatter(np.log10(cv["pop"]), cv["oda_pc"], s=400, marker="*",
           color="gold", edgecolors="black", zorder=5,
           label="Cabo Verde (2026 World Cup!)")

ax.set_xlabel("Population (log scale)")
ax.set_ylabel("ODA received per person, 2023 (USD)")
ax.set_title("The African aid & surveillance landscape\nBubble size = outbreak reports | Color = USAID share")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)
ax.set_xticks([6, 7, 8, 9]); ax.set_xticklabels(["1M", "10M", "100M", "1B"])
plt.tight_layout()
plt.savefig("analysis/fig_bubble_landscape.png", dpi=150, bbox_inches="tight")
print("Saved analysis/fig_bubble_landscape.png")
plt.close()