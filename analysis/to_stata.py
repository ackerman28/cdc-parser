import pandas as pd
import re

df = pd.read_excel("analysis/Africa_CDC_Merged_v3.xlsx")

# Stata variable names: letters/numbers/underscores only, max 32 chars, can't start with a digit
def clean_name(c):
    c = str(c).strip().lower()
    c = re.sub(r"[^0-9a-zA-Z]+", "_", c)
    c = re.sub(r"_+", "_", c).strip("_")
    if c and c[0].isdigit():
        c = "v_" + c
    return c[:32]

seen, new_cols, mapping = {}, [], {}
for c in df.columns:
    nc = clean_name(c)
    if nc in seen:
        seen[nc] += 1
        nc = f"{nc[:29]}_{seen[nc]}"
    else:
        seen[nc] = 0
    mapping[c] = nc
    new_cols.append(nc)
df.columns = new_cols

df.to_stata("analysis/Africa_CDC_Merged_v3.dta", write_index=False, version=118)
print("Saved analysis/Africa_CDC_Merged_v3.dta")

print("\nColumn name mapping (Stata name <- original):")
for orig, new in mapping.items():
    print(f"  {new:32} <- {orig}")