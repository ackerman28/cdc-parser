import pandas as pd
import matplotlib.pyplot as plt

dropouts = pd.read_csv("analysis/measles_dropouts_table.csv")
dropouts.columns = ["Country", "Measles (before)", "Measles (after)",
                    "Other diseases (after)", "USAID share"]

fig, ax = plt.subplots(figsize=(12, 3.2))   # wider figure
ax.axis("off")
fig.patch.set_facecolor("white")

tbl = ax.table(
    cellText=dropouts.values,
    colLabels=dropouts.columns,
    cellLoc="center",
    loc="center",
    colWidths=[0.30, 0.16, 0.16, 0.22, 0.16],  # give Country column the most room
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(11)
tbl.scale(1, 1.6)

for j in range(len(dropouts.columns)):
    cell = tbl[0, j]
    cell.set_facecolor("#2c3e50")
    cell.set_text_props(color="white", fontweight="bold")

for (row, col), cell in tbl.get_celld().items():
    if row > 0:
        cell.set_facecolor("white")

plt.title("Countries that stopped reporting measles after the Jan 2025 freeze\n"
          "(but kept reporting other diseases)", fontsize=11, pad=14)
plt.savefig("analysis/measles_dropouts_table.png", dpi=200,
            bbox_inches="tight", facecolor="white")
print("Saved analysis/measles_dropouts_table.png")
plt.close()