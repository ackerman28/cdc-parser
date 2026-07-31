import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_excel("analysis/Africa_CDC_Merged_v3.xlsx")
# Drop OCR-garbled UNKNOWN rows before any deaths/case math
clean = df[~df["Agent/Syndrome"].astype(str).str.startswith("UNKNOWN")].copy()

# ===== FIG 1: Case fatality rate by disease =====
g = clean.groupby("Agent/Syndrome").agg(conf=("new_confirmed", "sum"),
                                        deaths=("new_deaths", "sum"))
g = g[g["conf"] >= 100]                      # need enough cases for a stable rate
g["CFR"] = g["deaths"] / g["conf"] * 100
g = g.drop("Avian influenza", errors="ignore")   # known extraction error
g = g.sort_values("CFR", ascending=True).tail(8)

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(g.index, g["CFR"], color="#c0392b")
for b, v in zip(bars, g["CFR"]):
    ax.text(v + 0.4, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=9)
ax.set_xlabel("Case fatality rate (%)")
ax.set_title("Which diseases are deadliest?\nCase fatality rate = deaths / confirmed cases (2023–26)")
ax.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig("analysis/fig_cfr.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved fig_cfr.png")

# ===== FIG 2: Top reporters, Mali highlighted =====
tr = clean["Country"].value_counts().head(12).sort_values()
colors = ["#e67e22" if c == "Mali" else "#3498db" for c in tr.index]
fig, ax = plt.subplots(figsize=(10, 7))
ax.barh(tr.index, tr.values, color=colors)
ax.set_xlabel("Total outbreak reports (2023–26)")
ax.set_title("Surveillance activity by country\nMali reports far more than any other nation")
ax.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig("analysis/fig_top_reporters.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved fig_top_reporters.png")

# ===== FIG 3: Cholera epicenters (by confirmed cases) =====
ch = clean[clean["Agent/Syndrome"] == "Vibrio cholerae"]
che = ch.groupby("Country")["new_confirmed"].sum().sort_values(ascending=True).tail(10)
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(che.index, che.values, color="#16a085")
ax.set_xlabel("Total confirmed cholera cases")
ax.set_title("Cholera burden by country\nZimbabwe & Mozambique are the epicenters")
ax.grid(True, axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig("analysis/fig_cholera_epicenter.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved fig_cholera_epicenter.png")