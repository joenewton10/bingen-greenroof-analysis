"""
Generate the 10 figures referenced in THESIS_FINAL.md from the (updated)
synchronized_data_filtered table. Filenames match the thesis List of Figures so the
references resolve. Cluster logic is replicated from
dashboard/analysis.py::create_condition_categories (temp_diff_1 basis); the day/night
split uses radiation_balance_parkplatz < 0.

Run:  .venv/Scripts/python.exe scripts/thesis_generate_figures.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from dashboard.analysis import BingenGreenRoofAnalyzer  # noqa: E402

OUT = PROJECT_ROOT / "outputs"
OUT.mkdir(exist_ok=True)
TABLE = "synchronized_data_filtered"
sns.set_theme(style="whitegrid")

analyzer = BingenGreenRoofAnalyzer()
engine = analyzer.engine

print("Loading data from DB ...")
with engine.connect() as c:
    df = pd.read_sql_query(text(f"""
        SELECT timestamp,
               avg_air_temperature_greenroof AS t,
               avg_air_humidity_1_greenroof AS rh,
               avg_wind_speed_greenroof AS wind,
               avg_global_radiation_greenroof AS solar,
               avg_soil_moisture_greenroof AS soil,
               radiation_balance_parkplatz AS radbal,
               temp_diff_1, temp_diff_2
        FROM {TABLE}
        WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    """), c)

print(f"Loaded {len(df):,} rows")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["hour"] = df["timestamp"].dt.hour
df["month"] = df["timestamp"].dt.month
df["season"] = df["month"].map({12: "Winter", 1: "Winter", 2: "Winter",
                                3: "Spring", 4: "Spring", 5: "Spring",
                                6: "Summer", 7: "Summer", 8: "Summer",
                                9: "Autumn", 10: "Autumn", 11: "Autumn"})
df["day_night"] = np.where(df["radbal"] < 0, "Night (rad<0)", "Day (rad>=0)")


def cat(s, lo, mid, lo_l, mid_l, hi_l):
    return np.select([s.isna(), s < lo, s < mid], ["Unknown", lo_l, mid_l], default=hi_l)


temp_cat = cat(df.t, 5.0, 30.0, "Dormant / Cold", "Growth / Comfort", "Heat Stress")
hum_cat = cat(df.rh, 40.0, 60.0, "Dry", "Optimal", "Humid")
wind_cat = cat(df.wind, 1.5, 5.0, "Calm Wind", "Moderate Wind", "High Wind")
solar_cat = cat(df.solar, 200.0, 600.0, "Overcast", "Partly Cloudy", "Clear Sky")
soil_cat = cat(df.soil, 13.0, 33.0, "Wilt Risk", "Optimal", "Saturation")
conds = [
    (temp_cat == "Heat Stress") & (solar_cat == "Clear Sky") & (soil_cat == "Wilt Risk"),
    (temp_cat == "Heat Stress") & (solar_cat == "Clear Sky") & (hum_cat == "Dry"),
    (temp_cat == "Heat Stress") & (wind_cat == "Calm Wind") & (hum_cat == "Dry"),
    (temp_cat == "Heat Stress") & (solar_cat == "Clear Sky") & (wind_cat == "Calm Wind"),
    (temp_cat == "Heat Stress") & (wind_cat == "High Wind"),
    (temp_cat == "Heat Stress") & (soil_cat == "Wilt Risk"),
    (temp_cat == "Growth / Comfort") & (soil_cat == "Optimal") & (solar_cat == "Partly Cloudy"),
    (temp_cat == "Dormant / Cold") & (wind_cat == "High Wind"),
    (solar_cat == "Clear Sky") & (wind_cat == "Calm Wind") & (temp_cat == "Growth / Comfort"),
    (soil_cat == "Saturation") & (temp_cat == "Growth / Comfort"),
    (hum_cat == "Humid") & (temp_cat == "Growth / Comfort"),
]
labels = ["Compound Triple Stress", "High ET Stress", "Urban Heat Island",
          "Extreme Heat Stress", "Heat Stress + High Wind", "Drought Stress",
          "Optimal Growth", "Cold + Wind Stress", "High Solar + Calm",
          "Saturated Growth", "High Humidity Growth"]
df["cond"] = np.select(conds, labels, default=temp_cat)

# cluster-level stats (full data)
df["mc"] = df.temp_diff_1 < -0.2
cl = df.groupby("cond").agg(mean_effect=("temp_diff_1", "mean"),
                            count=("temp_diff_1", "size"),
                            mc_pct=("mc", "mean")).reset_index()
cl = cl[cl["count"] >= 30].copy()
cl["mc_pct"] *= 100
cl = cl.sort_values("mean_effect")
clusters = cl["cond"].tolist()


def sign_colors(values):
    return ["#2E7D32" if v < 0 else "#C62828" for v in values]


saved = []


def save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(name)
    print("saved", name)


# 1) Basic statistics overview
try:
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    s = df.sample(min(len(df), 150000), random_state=42)
    ax[0, 0].hist(s.temp_diff_1, bins=120, color="#1565C0", alpha=0.8)
    ax[0, 0].axvline(0, color="k", ls="--"); ax[0, 0].set_title("temp_diff_1 (0.5 m) distribution"); ax[0, 0].set_xlim(-8, 8)
    ax[0, 1].hist(s.temp_diff_2, bins=120, color="#6A1B9A", alpha=0.8)
    ax[0, 1].axvline(0, color="k", ls="--"); ax[0, 1].set_title("temp_diff_2 (2.0 m) distribution"); ax[0, 1].set_xlim(-8, 8)
    ax[1, 0].boxplot([df.temp_diff_1.dropna(), df.temp_diff_2.dropna()], labels=["0.5 m", "2.0 m"], showfliers=False)
    ax[1, 0].axhline(0, color="r", ls="--"); ax[1, 0].set_title("Temperature signal box plots")
    eff = [(df.temp_diff_1 < 0).mean() * 100, (df.temp_diff_2 < 0).mean() * 100]
    b = ax[1, 1].bar(["0.5 m", "2.0 m"], eff, color=["#1565C0", "#6A1B9A"])
    ax[1, 1].axhline(50, color="grey", ls=":"); ax[1, 1].set_ylim(0, 70); ax[1, 1].set_ylabel("Cooling effectiveness (%)")
    ax[1, 1].set_title("Cooling effectiveness (% records < 0)")
    ax[1, 1].bar_label(b, fmt="%.1f%%")
    fig.suptitle("Green Roof Cooling Effectiveness — Basic Statistical Analysis (Jul 2020 – May 2026)", fontsize=13)
    save(fig, "temp_diff_overview_stats.png")
except Exception as e:
    print("FIG1 failed:", e)

# 2) Temporal analysis (hourly + monthly)
try:
    hourly = df.groupby("hour").agg(e1=("temp_diff_1", lambda x: (x < 0).mean() * 100),
                                    e2=("temp_diff_2", lambda x: (x < 0).mean() * 100)).reset_index()
    monthly = df.groupby("month").agg(e1=("temp_diff_1", lambda x: (x < 0).mean() * 100),
                                      e2=("temp_diff_2", lambda x: (x < 0).mean() * 100)).reset_index()
    fig, ax = plt.subplots(1, 2, figsize=(15, 5.5))
    ax[0].plot(hourly.hour, hourly.e1, "-o", label="0.5 m", color="#1565C0")
    ax[0].plot(hourly.hour, hourly.e2, "-o", label="2.0 m", color="#6A1B9A")
    ax[0].axhline(50, color="grey", ls=":"); ax[0].set_xlabel("Hour of day"); ax[0].set_ylabel("Cooling effectiveness (%)")
    ax[0].set_title("Cooling effectiveness by hour (peak ~21:00)"); ax[0].legend(); ax[0].set_xticks(range(0, 24, 2))
    mlabels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    x = np.arange(12)
    ax[1].bar(x - 0.2, monthly.e1, 0.4, label="0.5 m", color="#1565C0")
    ax[1].bar(x + 0.2, monthly.e2, 0.4, label="2.0 m", color="#6A1B9A")
    ax[1].axhline(50, color="grey", ls=":"); ax[1].set_xticks(x); ax[1].set_xticklabels(mlabels)
    ax[1].set_xlabel("Month"); ax[1].set_ylabel("Cooling effectiveness (%)")
    ax[1].set_title("Cooling effectiveness by month (peak September)"); ax[1].legend()
    fig.suptitle("Green Roof Cooling Effectiveness — Temporal Analysis", fontsize=13)
    save(fig, "temp_diff_overview_stats_temp.png")
except Exception as e:
    print("FIG2 failed:", e)

# 3) Mean cooling effect bar chart by cluster
try:
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(cl.cond, cl.mean_effect, color=sign_colors(cl.mean_effect))
    ax.axvline(0, color="k"); ax.set_xlabel("Mean cooling effect temp_diff_1 (°C)")
    ax.set_title("Mean Cooling Effect Across Complex Conditions (negative = cooling)")
    save(fig, "Figure_1_Cooling_Effectiveness_Bar_Chart.png")
except Exception as e:
    print("FIG3 failed:", e)

# 4) Distribution box plots by cluster (sampled)
try:
    parts = []
    for cond in clusters:
        sub = df[df.cond == cond]
        parts.append(sub.sample(min(len(sub), 5000), random_state=1))
    samp = pd.concat(parts)
    order = clusters
    fig, ax = plt.subplots(figsize=(13, 8))
    sns.boxplot(data=samp, y="cond", x="temp_diff_1", order=order, showfliers=False, ax=ax, color="#90CAF9")
    ax.axvline(0, color="r", ls="--"); ax.set_xlim(-6, 6)
    ax.set_xlabel("temp_diff_1 (°C)"); ax.set_ylabel("")
    ax.set_title("Cooling Distribution by Complex Condition (sampled)")
    save(fig, "Figure_2_Cooling_Distribution_Boxplots.png")
except Exception as e:
    print("FIG4 failed:", e)

# 5) Meaningful cooling frequency by cluster
try:
    clf = cl.sort_values("mc_pct", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 7))
    b = ax.barh(clf.cond, clf.mc_pct, color="#00838F")
    ax.set_xlabel("Meaningful cooling frequency (% records < -0.2 °C)")
    ax.set_title("Meaningful Cooling Frequency by Complex Condition")
    ax.bar_label(b, fmt="%.1f%%", padding=3)
    save(fig, "Figure_3_Cooling_Frequency_Analysis.png")
except Exception as e:
    print("FIG5 failed:", e)

# 6) Performance matrix (scatter)
try:
    fig, ax = plt.subplots(figsize=(11, 8))
    sizes = (cl["count"] / cl["count"].max() * 1500) + 30
    ax.scatter(cl.mc_pct, cl.mean_effect, s=sizes, c=sign_colors(cl.mean_effect), alpha=0.6, edgecolors="k")
    ax.axhline(0, color="k", ls="--")
    for _, r in cl.iterrows():
        ax.annotate(r.cond, (r.mc_pct, r.mean_effect), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Meaningful cooling frequency (%)"); ax.set_ylabel("Mean cooling effect (°C)")
    ax.set_title("Performance Matrix — Mean Effect vs Cooling Frequency (point size ∝ n)")
    save(fig, "Figure_4_Performance_Matrix.png")
except Exception as e:
    print("FIG6 failed:", e)

# 7) Seasonal variation of top cooling clusters
try:
    top = cl.nsmallest(4, "mean_effect")["cond"].tolist()
    sv = df[df.cond.isin(top)].groupby(["cond", "season"])["temp_diff_1"].mean().reset_index()
    sorder = ["Winter", "Spring", "Summer", "Autumn"]
    sv["season"] = pd.Categorical(sv["season"], categories=sorder, ordered=True)
    piv = sv.pivot(index="season", columns="cond", values="temp_diff_1").reindex(sorder)
    fig, ax = plt.subplots(figsize=(11, 6))
    piv.plot(kind="bar", ax=ax); ax.axhline(0, color="k")
    ax.set_ylabel("Mean cooling effect (°C)"); ax.set_xlabel("Season")
    ax.set_title("Seasonal Variation — Top Cooling Conditions"); ax.legend(fontsize=8)
    save(fig, "Figure_5_Seasonal_Variation.png")
except Exception as e:
    print("FIG7 failed:", e)

# 8) Condition distribution (occurrence %)
try:
    occ = (df.cond.value_counts() / len(df) * 100).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(11, 7))
    b = ax.barh(occ.index, occ.values, color="#5E35B1")
    ax.set_xlabel("Occurrence (% of records)"); ax.set_title("Distribution of Complex Condition Occurrences")
    ax.bar_label(b, fmt="%.1f%%", padding=3)
    save(fig, "Figure_6_Condition_Distribution.png")
except Exception as e:
    print("FIG8 failed:", e)

# 9) Stress conditions seasonal variation
try:
    kws = ["Stress", "Compound", "High ET", "Urban Heat", "Drought", "Extreme", "High Solar"]
    stress = [c for c in clusters if any(k in c for k in kws)]
    sv = df[df.cond.isin(stress)].groupby(["cond", "season"]).agg(
        mean_effect=("temp_diff_1", "mean")).reset_index()
    sorder = ["Winter", "Spring", "Summer", "Autumn"]
    sv["season"] = pd.Categorical(sv["season"], categories=sorder, ordered=True)
    piv = sv.pivot(index="season", columns="cond", values="mean_effect").reindex(sorder)
    fig, ax = plt.subplots(figsize=(12, 6))
    piv.plot(kind="bar", ax=ax); ax.axhline(0, color="k")
    ax.set_ylabel("Mean effect (°C)"); ax.set_xlabel("Season")
    ax.set_title("Stress Conditions — Seasonal Variation"); ax.legend(fontsize=8)
    save(fig, "Figure_7_Stress_Conditions_Seasonal_Variation.png")
except Exception as e:
    print("FIG9 failed:", e)

# 10) Day/night regime split (radiation-based)
try:
    reg = df.groupby("day_night").agg(
        mean=("temp_diff_2", "mean"),
        mc=("temp_diff_2", lambda x: (x < -0.2).mean() * 100),
        mw=("temp_diff_2", lambda x: (x > 0.2).mean() * 100)).reset_index()
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))
    b0 = ax[0].bar(reg.day_night, reg["mean"], color=sign_colors(reg["mean"]))
    ax[0].axhline(0, color="k"); ax[0].set_ylabel("Mean temp_diff_2 (°C)")
    ax[0].set_title("Mean roof–reference signal by radiation regime"); ax[0].bar_label(b0, fmt="%.3f")
    x = np.arange(len(reg))
    ax[1].bar(x - 0.2, reg.mc, 0.4, label="Meaningful cooling %", color="#2E7D32")
    ax[1].bar(x + 0.2, reg.mw, 0.4, label="Meaningful warming %", color="#C62828")
    ax[1].set_xticks(x); ax[1].set_xticklabels(reg.day_night); ax[1].set_ylabel("% of records")
    ax[1].set_title("Cooling vs warming frequency by regime"); ax[1].legend()
    fig.suptitle("Day–Night Regime Split by Radiation Balance (temp_diff_2)", fontsize=13)
    save(fig, "regime_split_radiation.png")
except Exception as e:
    print("FIG10 failed:", e)

print(f"\nDone. {len(saved)}/10 figures saved to outputs/.")
