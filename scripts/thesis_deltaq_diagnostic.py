"""
Generate a single delta_q diagnostic figure for the v2 thesis.
Shows: (i) distribution of delta_q for parkplatz (full record) and for greenroof
(dual-level subset only, i.e. January 2024 onwards); (ii) scatter of delta_q
vs temp_diff_1 on a stratified sample, with separate panels per site.

Saves: outputs/Figure_DeltaQ_Diagnostic.png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.analysis import BingenGreenRoofAnalyzer  # noqa: E402

OUT = ROOT / "outputs"
TABLE = "synchronized_data_filtered"

a = BingenGreenRoofAnalyzer()
engine = a.engine

# sample for scatter (every 30th minute, ~72k rows)
with engine.connect() as c:
    df = pd.read_sql_query(text(f"""
        SELECT timestamp, temp_diff_1, delta_q_parkplatz, delta_q_roof, has_dual_level_greenroof
        FROM {TABLE}
        WHERE temp_diff_1 IS NOT NULL
          AND FLOOR(EXTRACT(EPOCH FROM timestamp)/60)::bigint % 30 = 0
    """), c)
print(f"loaded {len(df):,} rows for diagnostic")

fig, axes = plt.subplots(2, 2, figsize=(12, 9))

# Panel (a): histograms of delta_q
ax = axes[0, 0]
ax.hist(df.delta_q_parkplatz.dropna(), bins=120, range=(-2, 2), color="#1565C0", alpha=0.7, label="δq parkplatz")
ax.set_xlabel("δq_parkplatz (g/kg)")
ax.set_ylabel("count")
ax.set_title("δq distribution — parkplatz (full record)")
ax.axvline(0, color="k", lw=0.5)
ax.legend()

ax = axes[0, 1]
roof = df[df.has_dual_level_greenroof == True]["delta_q_roof"].dropna()
ax.hist(roof, bins=120, range=(-4, 4), color="#2E7D32", alpha=0.7, label="δq greenroof (Jan 2024+)")
ax.set_xlabel("δq_roof (g/kg)")
ax.set_ylabel("count")
ax.set_title(f"δq distribution — greenroof (dual-level period; n = {len(roof):,})")
ax.axvline(0, color="k", lw=0.5)
ax.legend()

# Panel (b): scatter of delta_q vs temp_diff_1
ax = axes[1, 0]
sub = df.dropna(subset=["delta_q_parkplatz", "temp_diff_1"])
if len(sub) > 50000:
    sub = sub.sample(50000, random_state=42)
ax.scatter(sub.delta_q_parkplatz, sub.temp_diff_1, alpha=0.1, s=3, color="#1565C0")
ax.axhline(0, color="k", lw=0.5)
ax.axvline(0, color="k", lw=0.5)
ax.set_xlim(-2, 2)
ax.set_ylim(-8, 8)
ax.set_xlabel("δq_parkplatz (g/kg)")
ax.set_ylabel("temp_diff_1 (°C)")
corr_pp = df[["delta_q_parkplatz", "temp_diff_1"]].dropna().corr().iloc[0, 1]
ax.set_title(f"δq_parkplatz vs temp_diff_1 (Spearman ρ ≈ {corr_pp:.3f})")

ax = axes[1, 1]
sub = df[df.has_dual_level_greenroof == True].dropna(subset=["delta_q_roof", "temp_diff_1"])
if len(sub) > 50000:
    sub = sub.sample(50000, random_state=42)
ax.scatter(sub.delta_q_roof, sub.temp_diff_1, alpha=0.1, s=3, color="#2E7D32")
ax.axhline(0, color="k", lw=0.5)
ax.axvline(0, color="k", lw=0.5)
ax.set_xlim(-4, 4)
ax.set_ylim(-8, 8)
ax.set_xlabel("δq_roof (g/kg)")
ax.set_ylabel("temp_diff_1 (°C)")
corr_gr = df[df.has_dual_level_greenroof == True][["delta_q_roof", "temp_diff_1"]].dropna().corr().iloc[0, 1]
ax.set_title(f"δq_roof vs temp_diff_1, dual-level only (Pearson r ≈ {corr_gr:.3f})")

fig.suptitle("Specific-humidity gradient (δq) diagnostic — Magnus formula, p = 1002 hPa", fontsize=12)
plt.tight_layout()
out = OUT / "Figure_DeltaQ_Diagnostic.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"saved {out.name}")
