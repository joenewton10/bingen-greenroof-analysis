"""
Recompute all headline thesis statistics from the (updated) synchronized_data_filtered
table. Reproduces the exact figures cited in THESIS_FINAL.md so the thesis can be
refreshed after a data update.

Cluster logic is replicated from dashboard/analysis.py::create_condition_categories
(temp_diff_1 basis). Day/night uses the radiation-based split (radiation_balance_parkplatz < 0)
on temp_diff_2, matching the original Chapter 4 "regime split" table.

Run:  .venv/Scripts/python.exe scripts/thesis_recompute_stats.py
"""
import sys
import json
import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, ".")
from dashboard.analysis import BingenGreenRoofAnalyzer  # noqa: E402

analyzer = BingenGreenRoofAnalyzer()
engine = analyzer.engine
TABLE = "synchronized_data_filtered"
out = {}


def q(sql):
    with engine.connect() as c:
        return pd.read_sql_query(text(sql), c)


# ---------------------------------------------------------------- aggregate
agg = q(f"""
    SELECT
        COUNT(*) FILTER (WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL) AS n_both,
        MIN(timestamp) AS min_ts,
        MAX(timestamp) AS max_ts,
        AVG(temp_diff_1) AS mean_td1,
        AVG(temp_diff_2) AS mean_td2,
        AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) AS cool_eff_1,
        AVG(CASE WHEN temp_diff_2 < 0 THEN 1.0 ELSE 0.0 END) AS cool_eff_2,
        CORR(temp_diff_1, temp_diff_2) AS corr_heights
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
""").iloc[0]

out["aggregate"] = {
    "n_both": int(agg.n_both),
    "min_ts": str(agg.min_ts),
    "max_ts": str(agg.max_ts),
    "mean_temp_diff_1": round(float(agg.mean_td1), 3),
    "mean_temp_diff_2": round(float(agg.mean_td2), 3),
    "cooling_eff_0.5m_pct": round(float(agg.cool_eff_1) * 100, 1),
    "cooling_eff_2.0m_pct": round(float(agg.cool_eff_2) * 100, 1),
    "corr_heights": round(float(agg.corr_heights), 3),
}

# ----------------------------------------------------- day/night (radiation)
# night := radiation_balance_parkplatz < 0 ; metric column = temp_diff_2
dn = q(f"""
    SELECT
        CASE WHEN radiation_balance_parkplatz < 0 THEN 'NIGHT' ELSE 'DAY' END AS regime,
        COUNT(*) AS n,
        AVG(temp_diff_2) AS mean,
        STDDEV_SAMP(temp_diff_2) AS std,
        MIN(temp_diff_2) AS min,
        MAX(temp_diff_2) AS max,
        AVG(CASE WHEN temp_diff_2 > 0 THEN 1.0 ELSE 0.0 END) AS failure,
        AVG(CASE WHEN temp_diff_2 < -0.2 THEN 1.0 ELSE 0.0 END) AS meaningful_cooling,
        AVG(CASE WHEN temp_diff_2 BETWEEN -0.2 AND 0.2 THEN 1.0 ELSE 0.0 END) AS within_error,
        AVG(CASE WHEN temp_diff_2 > 0.2 THEN 1.0 ELSE 0.0 END) AS meaningful_warming
    FROM {TABLE}
    WHERE temp_diff_2 IS NOT NULL AND radiation_balance_parkplatz IS NOT NULL
    GROUP BY 1
""")
out["day_night"] = {}
for _, r in dn.iterrows():
    out["day_night"][r.regime] = {
        "n": int(r.n),
        "mean": round(float(r["mean"]), 3),
        "std": round(float(r["std"]), 3),
        "min": round(float(r["min"]), 3),
        "max": round(float(r["max"]), 3),
        "failure_pct": round(float(r.failure) * 100, 1),
        "meaningful_cooling_pct": round(float(r.meaningful_cooling) * 100, 1),
        "within_error_pct": round(float(r.within_error) * 100, 1),
        "meaningful_warming_pct": round(float(r.meaningful_warming) * 100, 1),
    }

# ---------------------------------------------------- hourly cooling effect
hourly = q(f"""
    SELECT EXTRACT(HOUR FROM timestamp)::int AS hour,
           AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff1,
           AVG(CASE WHEN temp_diff_2 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff2,
           COUNT(*) AS n
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1 ORDER BY 1
""")
hourly["eff_min"] = hourly[["eff1", "eff2"]].min(axis=1)
hourly["eff_max"] = hourly[["eff1", "eff2"]].max(axis=1)
best_hr = hourly.loc[hourly[["eff1", "eff2"]].mean(axis=1).idxmax()]
out["best_hour"] = {
    "hour": int(best_hr.hour),
    "eff_0.5m_pct": round(float(best_hr.eff1), 1),
    "eff_2.0m_pct": round(float(best_hr.eff2), 1),
}
out["hourly_table"] = hourly.round(1).to_dict(orient="records")

# ---------------------------------------------------- monthly cooling effect
monthly = q(f"""
    SELECT EXTRACT(MONTH FROM timestamp)::int AS month,
           AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff1,
           AVG(CASE WHEN temp_diff_2 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff2,
           COUNT(*) AS n
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1 ORDER BY 1
""")
best_mo = monthly.loc[monthly[["eff1", "eff2"]].mean(axis=1).idxmax()]
out["best_month"] = {
    "month": int(best_mo.month),
    "eff_0.5m_pct": round(float(best_mo.eff1), 1),
    "eff_2.0m_pct": round(float(best_mo.eff2), 1),
}
out["monthly_table"] = monthly.round(1).to_dict(orient="records")

# ------------------------------------------- complex condition clusters
# Replicate dashboard/analysis.py::create_condition_categories on a lean column set.
cols = q(f"""
    SELECT avg_air_temperature_greenroof AS t,
           avg_air_humidity_1_greenroof AS rh,
           avg_wind_speed_greenroof AS wind,
           avg_global_radiation_greenroof AS solar,
           avg_soil_moisture_greenroof AS soil,
           temp_diff_1
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL
""")


def cat(s, lo, mid, lo_l, mid_l, hi_l):
    return np.select(
        [s.isna(), s < lo, s < mid],
        ["Unknown", lo_l, mid_l],
        default=hi_l,
    )


temp_cat = cat(cols.t, 5.0, 30.0, "Dormant / Cold", "Growth / Comfort", "Heat Stress")
hum_cat = cat(cols.rh, 40.0, 60.0, "Dry", "Optimal", "Humid")
wind_cat = cat(cols.wind, 1.5, 5.0, "Calm Wind", "Moderate Wind", "High Wind")
solar_cat = cat(cols.solar, 200.0, 600.0, "Overcast", "Partly Cloudy", "Clear Sky")
soil_cat = cat(cols.soil, 13.0, 33.0, "Wilt Risk", "Optimal", "Saturation")

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
labels = [
    "Compound Triple Stress", "High ET Stress", "Urban Heat Island",
    "Extreme Heat Stress", "Heat Stress + High Wind", "Drought Stress",
    "Optimal Growth", "Cold + Wind Stress", "High Solar + Calm",
    "Saturated Growth", "High Humidity Growth",
]
cols["cond"] = np.select(conds, labels, default=temp_cat)
cols["meaningful_cooling"] = cols.temp_diff_1 < -0.2

grp = cols.groupby("cond").agg(
    mean_effect=("temp_diff_1", "mean"),
    count=("temp_diff_1", "size"),
    meaningful_cooling_pct=("meaningful_cooling", "mean"),
)
grp = grp[grp["count"] >= 30]
grp["mean_effect"] = grp["mean_effect"].round(3)
grp["meaningful_cooling_pct"] = (grp["meaningful_cooling_pct"] * 100).round(1)
grp = grp.sort_values("mean_effect")

out["clusters"] = grp.reset_index().to_dict(orient="records")
best = grp.iloc[0]
worst = grp.iloc[-1]
out["best_cluster"] = {"name": best.name, "mean": float(best.mean_effect),
                       "meaningful_cooling_pct": float(best.meaningful_cooling_pct),
                       "n": int(best["count"])}
out["worst_cluster"] = {"name": worst.name, "mean": float(worst.mean_effect),
                        "meaningful_cooling_pct": float(worst.meaningful_cooling_pct),
                        "n": int(worst["count"])}

# ----------------------------------------------------- LAYER 2: seasonal (4 seasons)
season_sql = f"""
    SELECT
        CASE
            WHEN EXTRACT(MONTH FROM timestamp) IN (12,1,2) THEN 'Winter'
            WHEN EXTRACT(MONTH FROM timestamp) IN (3,4,5)  THEN 'Spring'
            WHEN EXTRACT(MONTH FROM timestamp) IN (6,7,8)  THEN 'Summer'
            ELSE 'Autumn'
        END AS season,
        COUNT(*) AS n,
        AVG(temp_diff_1) AS mean1,
        AVG(temp_diff_2) AS mean2,
        AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff1,
        AVG(CASE WHEN temp_diff_2 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff2,
        AVG(CASE WHEN temp_diff_2 < -0.2 THEN 1.0 ELSE 0.0 END) * 100 AS mc2,
        AVG(CASE WHEN temp_diff_2 > 0.2  THEN 1.0 ELSE 0.0 END) * 100 AS mw2
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1
"""
seasonal = q(season_sql)
seasonal = seasonal.set_index("season").reindex(["Winter", "Spring", "Summer", "Autumn"]).reset_index()
out["layer2_seasonal"] = seasonal.round(3).to_dict(orient="records")

# Growing (Apr-Sep) vs Cold (Oct-Mar)
growing_sql = f"""
    SELECT
        CASE WHEN EXTRACT(MONTH FROM timestamp) BETWEEN 4 AND 9 THEN 'Growing_Apr_Sep' ELSE 'Cold_Oct_Mar' END AS period,
        COUNT(*) AS n,
        AVG(temp_diff_1) AS mean1,
        AVG(temp_diff_2) AS mean2,
        AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff1,
        AVG(CASE WHEN temp_diff_2 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff2
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1
"""
out["layer2_growing_vs_cold"] = q(growing_sql).round(3).to_dict(orient="records")

# ----------------------------------------------------- LAYER 3: year-by-year with 95% CI
yearly_sql = f"""
    SELECT EXTRACT(YEAR FROM timestamp)::int AS year,
           COUNT(*) AS n,
           AVG(temp_diff_1) AS mean1,
           STDDEV_SAMP(temp_diff_1) AS std1,
           AVG(temp_diff_2) AS mean2,
           STDDEV_SAMP(temp_diff_2) AS std2,
           AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff1,
           AVG(CASE WHEN temp_diff_2 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff2
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1 ORDER BY 1
"""
yearly = q(yearly_sql)
yearly["sem1"] = yearly.std1 / np.sqrt(yearly.n.clip(lower=1))
yearly["ci_low1"] = yearly.mean1 - 1.96 * yearly.sem1
yearly["ci_high1"] = yearly.mean1 + 1.96 * yearly.sem1
yearly["sig_vs_zero"] = (yearly.ci_low1 > 0) | (yearly.ci_high1 < 0)
full_mean1 = out["aggregate"]["mean_temp_diff_1"]
yearly["diff_vs_full_period_mean"] = yearly.mean1 - full_mean1
yearly["sig_vs_full_period"] = (yearly.mean1 - 1.96 * yearly.sem1 > full_mean1) | (yearly.mean1 + 1.96 * yearly.sem1 < full_mean1)
out["layer3_yearly"] = yearly.round(4).to_dict(orient="records")

# ----------------------------------------------------- LAYER 4: monthly within each year
year_month_sql = f"""
    SELECT EXTRACT(YEAR FROM timestamp)::int AS year,
           EXTRACT(MONTH FROM timestamp)::int AS month,
           COUNT(*) AS n,
           AVG(temp_diff_1) AS mean1,
           AVG(temp_diff_2) AS mean2,
           AVG(CASE WHEN temp_diff_1 < 0 THEN 1.0 ELSE 0.0 END) * 100 AS eff1
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2
"""
out["layer4_year_month"] = q(year_month_sql).round(3).to_dict(orient="records")

# ----------------------------------------------------- delta_q stats (Magnus/specific humidity)
try:
    dq_sql = f"""
        SELECT
            AVG(delta_q_parkplatz) AS mean_dq_pp,
            STDDEV_SAMP(delta_q_parkplatz) AS std_dq_pp,
            COUNT(delta_q_parkplatz) AS n_dq_pp,
            AVG(delta_q_roof) FILTER (WHERE has_dual_level_greenroof) AS mean_dq_gr,
            STDDEV_SAMP(delta_q_roof) FILTER (WHERE has_dual_level_greenroof) AS std_dq_gr,
            COUNT(delta_q_roof) FILTER (WHERE has_dual_level_greenroof) AS n_dq_gr,
            CORR(delta_q_parkplatz, temp_diff_1) AS corr_dq_pp_td1,
            CORR(delta_q_roof, temp_diff_1) FILTER (WHERE has_dual_level_greenroof) AS corr_dq_gr_td1
        FROM {TABLE}
    """
    dq = q(dq_sql).iloc[0]
    out["delta_q_stats"] = {
        "parkplatz": {
            "mean_g_per_kg": round(float(dq.mean_dq_pp) if dq.mean_dq_pp is not None else 0.0, 4),
            "std_g_per_kg": round(float(dq.std_dq_pp) if dq.std_dq_pp is not None else 0.0, 4),
            "n": int(dq.n_dq_pp) if dq.n_dq_pp is not None else 0,
        },
        "greenroof_dual_level_only": {
            "mean_g_per_kg": round(float(dq.mean_dq_gr) if dq.mean_dq_gr is not None else 0.0, 4),
            "std_g_per_kg": round(float(dq.std_dq_gr) if dq.std_dq_gr is not None else 0.0, 4),
            "n": int(dq.n_dq_gr) if dq.n_dq_gr is not None else 0,
        },
        "correlations_with_temp_diff_1": {
            "parkplatz": round(float(dq.corr_dq_pp_td1) if dq.corr_dq_pp_td1 is not None else 0.0, 3),
            "greenroof": round(float(dq.corr_dq_gr_td1) if dq.corr_dq_gr_td1 is not None else 0.0, 3),
        },
    }
except Exception as e:
    out["delta_q_stats"] = {"error": f"delta_q columns not yet present: {e}"}

# ----------------------------------------------------- radiation components seasonal
rad_sql = f"""
    SELECT
        CASE
            WHEN EXTRACT(MONTH FROM timestamp) IN (12,1,2) THEN 'Winter'
            WHEN EXTRACT(MONTH FROM timestamp) IN (3,4,5)  THEN 'Spring'
            WHEN EXTRACT(MONTH FROM timestamp) IN (6,7,8)  THEN 'Summer'
            ELSE 'Autumn'
        END AS season,
        AVG(avg_global_radiation_greenroof) AS sw_in_gr, AVG(avg_sr2_greenroof) AS sw_out_gr,
        AVG(avg_ir1_greenroof) AS lw_in_gr,             AVG(avg_ir2_greenroof) AS lw_out_gr,
        AVG(avg_sr1_parkplatz) AS sw_in_pp,             AVG(avg_sr2_parkplatz) AS sw_out_pp,
        AVG(avg_ir1_parkplatz) AS lw_in_pp,             AVG(avg_ir2_parkplatz) AS lw_out_pp,
        AVG(radiation_balance_greenroof) AS rnet_gr,    AVG(radiation_balance_parkplatz) AS rnet_pp,
        AVG(albedo_greenroof) AS alb_gr,                AVG(albedo_parkplatz) AS alb_pp,
        COUNT(*) AS n
    FROM {TABLE}
    WHERE temp_diff_1 IS NOT NULL
    GROUP BY 1
"""
rad = q(rad_sql).set_index("season").reindex(["Winter", "Spring", "Summer", "Autumn"]).reset_index()
out["radiation_seasonal"] = rad.round(2).to_dict(orient="records")

print(json.dumps(out, indent=2, default=str))
