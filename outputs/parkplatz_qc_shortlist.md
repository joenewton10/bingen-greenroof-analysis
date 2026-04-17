# Parkplatz QC Shortlist

This shortlist is based on non-NaN min/max values from `ingested_parkplatz` and is meant to help decide which fields are usable for QC thresholds versus which ones are dominated by parsing/scaling artifacts.

## Usable with Standard QC

These fields show at least some physically plausible values and can be filtered with standard environmental bounds.

| Field | Non-NaN Min | Non-NaN Max | Assessment | Practical QC Direction |
|---|---:|---:|---|---|
| `air_temp_1_c` | -29.62 | 41935872000.0 | Mixed: plausible lows, extreme broken highs | Keep strict range like `[-25, 45]` |
| `air_temp_2_c` | -1568000.0 | 38810000.0 | Mixed: many broken values | Keep strict range like `[-25, 45]` |
| `soil_temp_1_c` | -103.286 | 48878000.0 | Mixed: many broken values | Keep strict range like `[-10, 50]` or `[-20, 50]` |
| `soil_temp_2_c` | -273.139 | 40629000.0 | Mixed: many broken values, sensor/dropout artifacts | Keep strict range like `[-10, 50]` or allow sentinel if justified |
| `air_humidity_1_rh` | 0.0 | 95212000.0 | Plausible low end, broken highs | Keep strict range `[0, 100]` |
| `air_humidity_2_rh` | 0.0 | 94738000.0 | Plausible low end, broken highs | Keep strict range `[0, 100]` |
| `wind_speed_ms` | -18.558 | 4024000.0 | Mixed: broken negatives/highs | Keep strict range `[0, 50]` |
| `wind_direction_deg` | -89.933 | 351431000.0 | Mixed: broken negatives/highs | Keep strict range `[0, 360]` |
| `soil_moisture_vol` | 0.0 | 18249000.0 | Plausible low end, broken highs | Keep strict range `[0, 100]` |
| `internal_temp_c` | -14.25 | 53890000 | Mixed | Keep permissive range like `[-30, 80]` |
| `battery_voltage_v` | 3.65 | 14590000 | Mixed | Keep practical device range like `[8, 16]` |
| `rain_rel_mm` | 0.0 | 1.0 | Looks plausible | Current bound is fine |

## Radiation Channels: Special Case

These fields should **not** be interpreted from raw min/max alone because sign convention and scaling artifacts are mixed together.

| Field | Non-NaN Min | Non-NaN Max | Assessment | Practical QC Direction |
|---|---:|---:|---|---|
| `ir1_wm2` | -120199000.0 | 70.502 | Sign/scaling issue dominates raw field | Do **not** use strict `>= -5` until sign is normalized or source behavior is confirmed |
| `ir2_wm2` | -83.07 | 90218000.0 | Mixed sign/scaling artifacts | Keep permissive outgoing bound; treat raw extremes as broken parsing/scaling |
| `sr1_wm2` | -83.238 | 1200875000 | Mostly plausible conceptually, but huge scaling artifacts exist | Incoming shortwave can still use near-zero lower bound if parser/scaling issues are separately removed |
| `sr2_wm2` | -0.257 | 179691000.0 | Mixed scaling artifacts | Outgoing/reflected bound should stay permissive |

## Clearly Broken / Not Suitable for Direct Physical Thresholding

These fields are dominated by counters, metadata-like values, or scaling artifacts and should not drive physical QC thresholds.

| Field | Non-NaN Min | Non-NaN Max | Assessment |
|---|---:|---:|---|
| `counter_1_impulses` | 3884 | 6336000000 | Counter, not environmental range |
| `counter_diff_impulses` | 0 | 1000000.0 | Counter, not environmental range |
| `rain_abs_mm` | 388.4 | 633600000 | Cumulative counter/scaling artifact mix |
| `duration_counting` | 4.0 | 4294964032.0 | Counter/system field |
| `field_strength_1` | 10.0 | 14000000 | System/telemetry field |
| `alarm_level` | 0 | 0 | Status field |

## High-Signal Takeaways

1. The parkplatz table contains substantial `NaN` contamination in many numeric columns.
2. Many environmental channels contain extreme positive values consistent with scaling/parsing problems.
3. Standard QC thresholds for temperature, humidity, wind, and soil moisture are still reasonable because they remove these artifacts effectively.
4. `IR1` is the most important special case: a strict incoming threshold like `>= -5` removes too much data because the raw sign convention or encoding is not aligned with that assumption.
5. For presentation-safe processing, keep the professor's correction for outgoing channels (`IR2`, `SR2`) but treat `IR1` more cautiously until sign normalization is implemented.

## Recommended Immediate QC Strategy

1. Keep standard physical ranges for temperature, humidity, wind, soil moisture, battery voltage, and rain interval.
2. Keep permissive outgoing radiation bounds for `ir2_wm2` and `sr2_wm2`.
3. Revisit `ir1_wm2` separately: either normalize sign first or temporarily relax the lower bound so valid records are not discarded.
4. Do not use raw maxima from parkplatz radiation fields as evidence for physical upper bounds; they are heavily affected by broken scaled values.