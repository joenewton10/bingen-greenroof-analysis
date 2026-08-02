"""
Generate Layer 5 case-study day figures for the thesis.

Selection rule:
    - Restrict to growing season (April-September)
    - Restrict to days with has_dual_level_greenroof = TRUE (so January 2024 onwards)
    - Rank candidate days by daily mean temp_diff_1
    - Take the 3 strongest cooling days and the 3 strongest warming days

For each chosen day, render a 4-panel matplotlib figure:
    (1) temp_diff_1 and temp_diff_2 vs hour
    (2) SW_in / SW_out / LW_in / LW_out for both sites
    (3) delta_T_roof and delta_q_roof (the gradients)
    (4) albedo_greenroof and albedo_parkplatz

Saves: outputs/case_study_YYYY-MM-DD_<cool|warm>.png  (6 PNGs)
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.analysis import BingenGreenRoofAnalyzer  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
TABLE = "synchronized_data_filtered"

a = BingenGreenRoofAnalyzer()
engine = a.engine


def q(sql):
    with engine.connect() as c:
        return pd.read_sql_query(text(sql), c)


print("Ranking candidate days...")
daily = q(f"""
    SELECT date_trunc('day', timestamp)::date AS day,
           AVG(temp_diff_1) AS mean_td1,
           AVG(temp_diff_2) AS mean_td2,
           COUNT(*) AS n
    FROM {TABLE}
    WHERE has_dual_level_greenroof = TRUE
      AND EXTRACT(MONTH FROM timestamp) BETWEEN 4 AND 9
      AND temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 1200   -- require >= 20 hours of valid data in the day
    ORDER BY 1
""")
print(f"  {len(daily)} candidate growing-season days with dual-level coverage")

cool = daily.nsmallest(3, "mean_td1")
warm = daily.nlargest(3, "mean_td1")
selected = pd.concat([cool.assign(kind="cool"), warm.assign(kind="warm")], ignore_index=True)

selection_log = []


def render_day(day, kind, mean_td1):
    day_str = pd.Timestamp(day).strftime("%Y-%m-%d")
    df = q(f"""
        SELECT timestamp, temp_diff_1, temp_diff_2,
               avg_global_radiation_greenroof AS sw_in_gr, avg_sr2_greenroof AS sw_out_gr,
               avg_ir1_greenroof AS lw_in_gr,           avg_ir2_greenroof AS lw_out_gr,
               avg_sr1_parkplatz AS sw_in_pp,           avg_sr2_parkplatz AS sw_out_pp,
               avg_ir1_parkplatz AS lw_in_pp,           avg_ir2_parkplatz AS lw_out_pp,
               delta_t_roof, delta_q_roof,
               albedo_greenroof, albedo_parkplatz
        FROM {TABLE}
        WHERE timestamp >= '{day_str}'::timestamp
          AND timestamp <  '{day_str}'::timestamp + INTERVAL '1 day'
        ORDER BY timestamp
    """)
    if df.empty:
        print(f"  WARN: no data for {day_str}")
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

    ax = axes[0]
    ax.plot(df.timestamp, df.temp_diff_1, color="#1565C0", label="0.5 m")
    ax.plot(df.timestamp, df.temp_diff_2, color="#6A1B9A", label="2.0 m", alpha=0.8)
    ax.axhline(0, color="k", lw=0.5)
    ax.fill_between(df.timestamp, -0.2, 0.2, alpha=0.08, color="grey", label="±0.2 °C band")
    ax.set_ylabel("temp_diff (°C)")
    ax.legend(loc="best", fontsize=8)
    ax.set_title(
        f"Case study: {day_str}  ({'strong cooling' if kind=='cool' else 'strong warming'}; "
        f"daily mean temp_diff_1 = {mean_td1:+.3f} °C)",
        fontsize=11,
    )

    ax = axes[1]
    ax.plot(df.timestamp, df.sw_in_gr, color="#FF8F00", label="SW_in GR")
    ax.plot(df.timestamp, df.sw_in_pp, color="#FF8F00", ls="--", label="SW_in PP")
    ax.plot(df.timestamp, df.sw_out_gr, color="#FFB300", label="SW_out GR")
    ax.plot(df.timestamp, df.sw_out_pp, color="#FFB300", ls="--", label="SW_out PP")
    ax.plot(df.timestamp, df.lw_in_gr, color="#C62828", label="LW_in GR")
    ax.plot(df.timestamp, df.lw_in_pp, color="#C62828", ls="--", label="LW_in PP")
    ax.plot(df.timestamp, df.lw_out_gr, color="#AD1457", label="LW_out GR")
    ax.plot(df.timestamp, df.lw_out_pp, color="#AD1457", ls="--", label="LW_out PP")
    ax.set_ylabel("Radiation (W/m²)")
    ax.legend(loc="best", fontsize=7, ncol=4)

    ax = axes[2]
    ax2 = ax.twinx()
    ax.plot(df.timestamp, df.delta_t_roof, color="#2E7D32", label="δT_roof (°C)")
    ax.axhline(0, color="#2E7D32", lw=0.3)
    ax2.plot(df.timestamp, df.delta_q_roof, color="#00838F", label="δq_roof (g/kg)")
    ax2.axhline(0, color="#00838F", lw=0.3)
    ax.set_ylabel("δT_roof (°C)", color="#2E7D32")
    ax2.set_ylabel("δq_roof (g/kg)", color="#00838F")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="best", fontsize=8)

    ax = axes[3]
    ax.plot(df.timestamp, df.albedo_greenroof, color="#2E7D32", label="albedo GR")
    ax.plot(df.timestamp, df.albedo_parkplatz, color="#1565C0", label="albedo PP", alpha=0.8)
    ax.set_ylabel("albedo")
    ax.set_xlabel("time (UTC)")
    ax.set_ylim(0, 0.6)
    ax.legend(loc="best", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout()
    fname = f"case_study_{day_str}_{kind}.png"
    fig.savefig(OUT / fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {fname}  (n_minutes = {len(df)})")
    return fname


print("\nRendering case-study figures...")
for _, row in selected.iterrows():
    fname = render_day(row.day, row.kind, float(row.mean_td1))
    selection_log.append({"day": str(row.day), "kind": row.kind, "mean_td1": float(row.mean_td1),
                          "mean_td2": float(row.mean_td2), "n_minutes": int(row.n), "file": fname})

with open(OUT / "case_study_selection.json", "w", encoding="utf-8") as f:
    json.dump(selection_log, f, indent=2, default=str)

print(f"\nDone. {len(selection_log)} case-study figures + selection log saved to outputs/.")
