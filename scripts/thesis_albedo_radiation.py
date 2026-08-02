"""
Compute the measured albedo and daytime net-radiation statistics reported in §4.8.

Albedo columns (SW_out / SW_in, computed only where SW_in >= 10 W/m^2) already exist
in the synchronized table. This script summarises them for both sites and the daytime
net-radiation balance, so the §4.8 numbers are traceable.

Run:  .venv/Scripts/python.exe scripts/thesis_albedo_radiation.py
Writes: outputs/thesis_albedo_radiation.json
"""
import sys
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.analysis import BingenGreenRoofAnalyzer  # noqa: E402

eng = BingenGreenRoofAnalyzer().engine
TABLE = "synchronized_data_filtered"
OUT = ROOT / "outputs" / "thesis_albedo_radiation.json"


def q(sql):
    with eng.connect() as c:
        return pd.read_sql_query(text(sql), c)


res = {}

# Paired albedo (both sites defined simultaneously): the fair head-to-head comparison
paired = q(f"""SELECT AVG(albedo_greenroof) mean_gr, AVG(albedo_parkplatz) mean_pp,
   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY albedo_greenroof) med_gr,
   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY albedo_parkplatz) med_pp,
   AVG(CASE WHEN albedo_greenroof > albedo_parkplatz THEN 1.0 ELSE 0.0 END) frac_gr_higher,
   COUNT(*) n
   FROM {TABLE}
   WHERE albedo_greenroof IS NOT NULL AND albedo_parkplatz IS NOT NULL""").iloc[0]

midday = q(f"""SELECT AVG(albedo_greenroof) mid_gr, AVG(albedo_parkplatz) mid_pp, COUNT(*) n
   FROM {TABLE}
   WHERE EXTRACT(HOUR FROM timestamp) BETWEEN 11 AND 14
     AND albedo_greenroof IS NOT NULL AND albedo_parkplatz IS NOT NULL""").iloc[0]

res["albedo"] = dict(
    note="paired = records where both site albedos are simultaneously defined (SW_in >= 10)",
    n_paired=int(paired.n),
    greenroof_mean=round(float(paired.mean_gr), 3), greenroof_median=round(float(paired.med_gr), 3),
    parkplatz_mean=round(float(paired.mean_pp), 3), parkplatz_median=round(float(paired.med_pp), 3),
    frac_greenroof_higher=round(float(paired.frac_gr_higher), 3),
    midday_11_14h=dict(greenroof=round(float(midday.mid_gr), 3),
                       parkplatz=round(float(midday.mid_pp), 3), n=int(midday.n)),
)

# Daytime net radiation and net shortwave (radiation_balance_parkplatz >= 0 as day proxy)
rad = q(f"""SELECT
   AVG(radiation_balance_greenroof) rnet_gr, AVG(radiation_balance_parkplatz) rnet_pp,
   AVG(avg_global_radiation_greenroof - avg_sr2_greenroof) netsw_gr,
   AVG(avg_sr1_parkplatz - avg_sr2_parkplatz) netsw_pp, COUNT(*) n
   FROM {TABLE}
   WHERE radiation_balance_parkplatz >= 0
     AND radiation_balance_greenroof IS NOT NULL AND radiation_balance_parkplatz IS NOT NULL""").iloc[0]

res["daytime_radiation_Wm2"] = dict(
    note="daytime := radiation_balance_parkplatz >= 0",
    n=int(rad.n),
    rnet_greenroof=round(float(rad.rnet_gr), 1), rnet_parkplatz=round(float(rad.rnet_pp), 1),
    net_shortwave_greenroof=round(float(rad.netsw_gr), 1),
    net_shortwave_parkplatz=round(float(rad.netsw_pp), 1),
)

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res, indent=2))
print(f"\nwrote {OUT}")
