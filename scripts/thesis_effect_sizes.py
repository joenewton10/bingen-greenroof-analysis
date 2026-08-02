"""
Compute the exact effect sizes reported in Chapter 4 (§4.8, §4.9) of the thesis.

Pure numpy/pandas rank formulas (no scipy dependency):
  - Day vs night: Mann-Whitney U -> Cohen's r = |Z| / sqrt(N)      (temp_diff_2, radiation split)
  - Condition clusters: Kruskal-Wallis H (tie-corrected) -> eta^2_H = (H - k + 1) / (N - k)   (temp_diff_1)
  - delta_q vs temp_diff_1: Spearman rho, overall and per regime

Day/night and cluster definitions replicate scripts/thesis_recompute_stats.py
(and therefore dashboard/analysis.py::create_condition_categories) exactly.

Run:  .venv/Scripts/python.exe scripts/thesis_effect_sizes.py
Writes: outputs/thesis_effect_sizes.json
"""
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.analysis import BingenGreenRoofAnalyzer  # noqa: E402

eng = BingenGreenRoofAnalyzer().engine
TABLE = "synchronized_data_filtered"
OUT = ROOT / "outputs" / "thesis_effect_sizes.json"


def q(sql):
    with eng.connect() as c:
        return pd.read_sql_query(text(sql), c)


def avg_rank(x):
    return pd.Series(x).rank(method="average").to_numpy()


def tie_sum(x):
    _, c = np.unique(x, return_counts=True)
    return float(np.sum(c ** 3 - c))


res = {}

# ---------------- Day vs night: Cohen's r from Mann-Whitney U ----------------
dn = q(f"""SELECT temp_diff_2 AS td2, (radiation_balance_parkplatz < 0) AS night
           FROM {TABLE}
           WHERE temp_diff_2 IS NOT NULL AND radiation_balance_parkplatz IS NOT NULL""")
allv = np.concatenate([dn.loc[dn.night, "td2"].to_numpy(), dn.loc[~dn.night, "td2"].to_numpy()])
n1 = int(dn.night.sum())
n2 = int((~dn.night).sum())
N = n1 + n2
ranks = avg_rank(allv)
R1 = ranks[:n1].sum()
U1 = R1 - n1 * (n1 + 1) / 2.0
mU = n1 * n2 / 2.0
sigma = np.sqrt((n1 * n2 / 12.0) * ((N + 1) - tie_sum(allv) / (N * (N - 1.0))))
Z = (U1 - mU) / sigma
res["day_night"] = dict(
    test="Mann-Whitney U on temp_diff_2, night := radiation_balance_parkplatz < 0",
    n_night=n1, n_day=n2,
    mean_night=round(float(dn.loc[dn.night, "td2"].mean()), 3),
    mean_day=round(float(dn.loc[~dn.night, "td2"].mean()), 3),
    Z=round(float(Z), 1),
    cohen_r=round(float(abs(Z) / np.sqrt(N)), 3),
    rank_biserial=round(float(1.0 - 2.0 * U1 / (n1 * n2)), 3),
)
del dn, allv, ranks

# ---------------- Clusters: Kruskal-Wallis + eta^2_H ----------------
cl = q(f"""SELECT avg_air_temperature_greenroof AS t, avg_air_humidity_1_greenroof AS rh,
                  avg_wind_speed_greenroof AS wind, avg_global_radiation_greenroof AS solar,
                  avg_soil_moisture_greenroof AS soil, temp_diff_1
           FROM {TABLE} WHERE temp_diff_1 IS NOT NULL""")


def cat(s, lo, mid, lo_l, mid_l, hi_l):
    return np.select([s.isna(), s < lo, s < mid], ["Unknown", lo_l, mid_l], default=hi_l)


temp_cat = cat(cl.t, 5.0, 30.0, "Dormant / Cold", "Growth / Comfort", "Heat Stress")
hum_cat = cat(cl.rh, 40.0, 60.0, "Dry", "Optimal", "Humid")
wind_cat = cat(cl.wind, 1.5, 5.0, "Calm Wind", "Moderate Wind", "High Wind")
solar_cat = cat(cl.solar, 200.0, 600.0, "Overcast", "Partly Cloudy", "Clear Sky")
soil_cat = cat(cl.soil, 13.0, 33.0, "Wilt Risk", "Optimal", "Saturation")
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
labels = ["Compound Triple Stress", "High ET Stress", "Urban Heat Island", "Extreme Heat Stress",
          "Heat Stress + High Wind", "Drought Stress", "Optimal Growth", "Cold + Wind Stress",
          "High Solar + Calm", "Saturated Growth", "High Humidity Growth"]
cl["cond"] = np.select(conds, labels, default=temp_cat)
vc = cl["cond"].value_counts()
sub = cl[cl["cond"].isin(vc[vc >= 30].index)].copy()
Nk = len(sub)
k = sub["cond"].nunique()
sub["rank"] = avg_rank(sub["temp_diff_1"].to_numpy())
Rsum = sub.groupby("cond")["rank"].sum()
nsz = sub.groupby("cond")["rank"].size()
H = 12.0 / (Nk * (Nk + 1)) * float((Rsum ** 2 / nsz).sum()) - 3.0 * (Nk + 1)
C = 1.0 - tie_sum(sub["temp_diff_1"].to_numpy()) / (Nk ** 3 - Nk)
H_c = H / C
res["clusters"] = dict(
    test="Kruskal-Wallis on temp_diff_1 across occupied condition clusters (n >= 30)",
    k=int(k), N=int(Nk), H=round(float(H_c), 1),
    eta2_H=round(float((H_c - k + 1) / (Nk - k)), 4),
)
del cl, sub

# ---------------- Spearman: delta_q vs temp_diff_1 ----------------
sp = q(f"""SELECT temp_diff_1 AS td1, delta_q_parkplatz AS dqp, delta_q_roof AS dqr,
                  (radiation_balance_parkplatz < 0) AS night, EXTRACT(MONTH FROM timestamp) AS mon
           FROM {TABLE} WHERE temp_diff_1 IS NOT NULL""")


def rho(a, b):
    a = pd.Series(a).reset_index(drop=True)
    b = pd.Series(b).reset_index(drop=True)
    m = a.notna() & b.notna()
    if int(m.sum()) < 100:
        return {"rho": None, "n": int(m.sum())}
    ra = a[m].rank(method="average").to_numpy()
    rb = b[m].rank(method="average").to_numpy()
    return {"rho": round(float(np.corrcoef(ra, rb)[0, 1]), 3), "n": int(m.sum())}


grow = sp.mon.between(4, 9)
res["spearman"] = dict(
    metric="Spearman rho between delta_q and temp_diff_1",
    dq_parkplatz_all=rho(sp.dqp, sp.td1),
    dq_roof_all=rho(sp.dqr, sp.td1),
    dq_parkplatz_night=rho(sp.dqp[sp.night], sp.td1[sp.night]),
    dq_parkplatz_day=rho(sp.dqp[~sp.night], sp.td1[~sp.night]),
    dq_parkplatz_growing=rho(sp.dqp[grow], sp.td1[grow]),
    dq_parkplatz_cold=rho(sp.dqp[~grow], sp.td1[~grow]),
)

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res, indent=2))
print(f"\nwrote {OUT}")
