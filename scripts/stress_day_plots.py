"""
Render per-day diagnostic figures for the worst High ET Stress and Extreme Heat
Stress days in the synchronized record.

Selection: top N days by total stressed minutes (union of High ET Stress and
Extreme Heat Stress), taken from outputs/stress_cluster_dates.csv.

For each chosen day, render a 4-panel figure:
    (1) temp_diff_1 and temp_diff_2 vs hour, with the ±0.2 sensor-error band
    (2) Four radiation components for both sites (SW_in, SW_out, LW_in, LW_out)
    (3) Vertical gradients: greenroof (delta_T_roof, delta_q_roof) where dual-level
        data exist (Jan 2024 onwards), parkplatz gradients (delta_T_pp, delta_q_pp)
        otherwise. The legend tells the reader which one is plotted.
    (4) Albedo for both sites

Saves: outputs/stress_day_YYYY-MM-DD.png
"""
import sys
from pathlib import Path

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
TABLE = "synchronized_data_filtered"
N_DAYS = 8  # top-N worst stress days to render

a = BingenGreenRoofAnalyzer()
engine = a.engine

# Read the previously saved per-day stress table
stress = pd.read_csv(OUT / "stress_cluster_dates.csv")
stress["date"] = pd.to_datetime(stress["date"]).dt.date
stress = stress.sort_values("total_minutes", ascending=False).head(N_DAYS)
print("Days to render:")
for _, r in stress.iterrows():
    print(f"  {r.date}  total={int(r.total_minutes)} min")


def render(day, summary_row):
    day_str = pd.Timestamp(day).strftime("%Y-%m-%d")
    with engine.connect() as c:
        df = pd.read_sql_query(text(f"""
            SELECT timestamp, temp_diff_1, temp_diff_2, has_dual_level_greenroof,
                   avg_global_radiation_greenroof AS sw_in_gr, avg_sr2_greenroof AS sw_out_gr,
                   avg_ir1_greenroof AS lw_in_gr,           avg_ir2_greenroof AS lw_out_gr,
                   avg_sr1_parkplatz AS sw_in_pp,           avg_sr2_parkplatz AS sw_out_pp,
                   avg_ir1_parkplatz AS lw_in_pp,           avg_ir2_parkplatz AS lw_out_pp,
                   delta_t_roof, delta_q_roof,
                   delta_t_parkplatz, delta_q_parkplatz,
                   albedo_greenroof, albedo_parkplatz
            FROM {TABLE}
            WHERE timestamp >= '{day_str}'::timestamp
              AND timestamp <  '{day_str}'::timestamp + INTERVAL '1 day'
            ORDER BY timestamp
        """), c)
    if df.empty:
        print(f"  WARN: no data for {day_str}")
        return
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    has_roof_grad = bool(df["has_dual_level_greenroof"].any())

    het = int(summary_row.get("High ET Stress_minutes", 0) or 0)
    ext = int(summary_row.get("Extreme Heat Stress_minutes", 0) or 0)
    het_mean = summary_row.get("High ET Stress_meanTD1")
    ext_mean = summary_row.get("Extreme Heat Stress_meanTD1")

    fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

    # (1) temp_diff
    ax = axes[0]
    ax.plot(df.timestamp, df.temp_diff_1, color="#1565C0", label="temp_diff (0.5 m)")
    ax.plot(df.timestamp, df.temp_diff_2, color="#6A1B9A", label="temp_diff (2.0 m)", alpha=0.8)
    ax.axhline(0, color="k", lw=0.5)
    ax.fill_between(df.timestamp, -0.2, 0.2, alpha=0.08, color="grey", label="±0.2 °C error band")
    ax.set_ylabel("temp_diff (°C)")
    ax.legend(loc="best", fontsize=8)
    parts = []
    if het > 0:
        m = f", mean {het_mean:+.2f} °C" if pd.notna(het_mean) else ""
        parts.append(f"High ET Stress {het} min{m}")
    if ext > 0:
        m = f", mean {ext_mean:+.2f} °C" if pd.notna(ext_mean) else ""
        parts.append(f"Extreme Heat Stress {ext} min{m}")
    ax.set_title(f"Stress day: {day_str}    " + " | ".join(parts), fontsize=11)

    # (2) radiation components
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

    # (3) gradients: roof if dual-level available, otherwise parkplatz
    ax = axes[2]
    ax2 = ax.twinx()
    if has_roof_grad:
        ax.plot(df.timestamp, df.delta_t_roof, color="#2E7D32", label="δT_roof (°C)")
        ax2.plot(df.timestamp, df.delta_q_roof, color="#00838F", label="δq_roof (g/kg)")
        ax.set_ylabel("δT_roof (°C)", color="#2E7D32")
        ax2.set_ylabel("δq_roof (g/kg)", color="#00838F")
        ax.set_title("Roof vertical gradients (dual-level greenroof, Jan 2024+)", fontsize=9, loc="left")
    else:
        ax.plot(df.timestamp, df.delta_t_parkplatz, color="#1565C0", label="δT_parkplatz (°C)")
        ax2.plot(df.timestamp, df.delta_q_parkplatz, color="#00838F", label="δq_parkplatz (g/kg)")
        ax.set_ylabel("δT_parkplatz (°C)", color="#1565C0")
        ax2.set_ylabel("δq_parkplatz (g/kg)", color="#00838F")
        ax.set_title("Parking-lot vertical gradients (greenroof dual-level unavailable on this day)",
                     fontsize=9, loc="left")
    ax.axhline(0, color="k", lw=0.3)
    ax2.axhline(0, color="k", lw=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="best", fontsize=8)

    # (4) albedo
    ax = axes[3]
    ax.plot(df.timestamp, df.albedo_greenroof, color="#2E7D32", label="albedo GR")
    ax.plot(df.timestamp, df.albedo_parkplatz, color="#1565C0", label="albedo PP", alpha=0.8)
    ax.set_ylabel("albedo")
    ax.set_xlabel("time (UTC)")
    ax.set_ylim(0, 0.6)
    ax.legend(loc="best", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    plt.tight_layout()
    out = OUT / f"stress_day_{day_str}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out.name}  (n_minutes={len(df)}, dual-level roof = {has_roof_grad})")


print()
print("Rendering...")
for _, row in stress.iterrows():
    render(row.date, row)

print("\nDone.")
