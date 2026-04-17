# Greenroof QC Shortlist

This shortlist is based on raw ingested ranges from `ingested_empower_greenroof` and `ingested_kissel_greenroof` and is meant to align the greenroof review with the parkplatz QC shortlist.

## Source Context

Greenroof is split across two sources:

1. `ingested_empower_greenroof` — includes the broader radiation and dual-level sensor set, but also contains several severe outliers.
2. `ingested_kissel_greenroof` — simpler schema, mostly cleaner, but many fields are absent (`NULL`) and a few channels exceed plausible environmental bounds.

## Usable with Standard QC

These fields show at least some physically plausible values and can be filtered with standard environmental bounds.

| Field | Observed Raw Range | Source Context | Assessment | Practical QC Direction |
|---|---|---|---|---|
| `air_temp_1` | Empower: `-29.54` to `48759150000.0`; Kissel: `-11.3` to `40.7` | Lower-level air temperature | Mixed: one source plausible, one source contains extreme highs | Keep strict range like `[-25, 45]` |
| `air_temp_2` | Empower: `-30.0` to `39.44`; Kissel: `NULL` | Upper-level air temperature | Empower looks usable; Kissel absent | Keep strict range like `[-25, 45]` |
| `air_humidity_1` | Empower: `0.0` to `99.73`; Kissel: `14.8` to `129.4` | Lower-level RH | Mostly usable, but Kissel exceeds 100 | Keep strict range `[0, 100]` |
| `air_humidity_2` | Empower: `0.0` to `99.965`; Kissel: `NULL` | Upper-level RH | Empower looks usable; Kissel absent | Keep strict range `[0, 100]` |
| `wind_speed` | Empower: `-18.553` to `11.513`; Kissel: `0.0` to `11.7` | Wind speed | Mostly plausible highs, broken negatives in Empower | Keep strict range `[0, 50]` |
| `wind_direction` | Empower: `-88.357` to `374.378`; Kissel: `0.0` to `359.9` | Wind direction | Mostly plausible, but broken negatives and slight overflow | Keep strict range `[0, 360]` |
| `soil_moisture` | Empower: `0.0` to `60605.0`; Kissel: `0.0` to `33.78` | Volumetric moisture | One source plausible, one source has extreme highs | Keep strict range like `[0, 60]` |
| `soil_temp_1` | Empower: `-0.317` to `22758.002`; Kissel: `-3.22` to `55.79` | Soil temperature | One source plausible, one source has extreme highs | Keep strict range like `[-20, 50]` |
| `soil_temp_2` | Empower: `-125050.008` to `26.261`; Kissel: `NULL` | Secondary soil temperature | Mixed, includes severe negative artifacts | Keep strict range and special-case sentinel where justified |
| `temperature` | Empower: `-45507.766` to `38.91`; Kissel: `NULL` | Generic temperature channel | Mixed, broken negatives present | Keep strict range like `[-25, 45]` |
| `air_pressure` | Empower: `0.0` to `1070940.0`; Kissel: `NULL` | Pressure | Mixed, plausible upper region exists but severe high scaling artifact too | Keep strict range like `[900, 1100]` |

## Radiation Channels: Special Case

These fields should not be interpreted from raw min/max alone because sign convention, source differences, and scaling artifacts are mixed together.

| Field | Observed Raw Range | Source Context | Assessment | Practical QC Direction |
|---|---|---|---|---|
| `ir1` | Empower: `-138.522` to `15.0`; Kissel: `NULL` | Incoming longwave | Raw sign is mostly negative in Empower, which conflicts with strict physical expectation | Do **not** force strict `>= -5` until sign convention is confirmed or normalized |
| `sr1` | Empower: `-1.935` to `1363.249`; Kissel: `-10.3` to `1336.5` | Incoming shortwave | Mostly plausible with moderate negatives and high daytime values | Near-zero lower bound is reasonable, but upper bound may need to allow real peaks |
| `ir2` | Empower: `-35.351` to `62.459`; Kissel: `NULL` | Outgoing longwave | Sign convention unclear from raw range alone; likely not yet normalized to desired outgoing convention | Keep outgoing treatment permissive and do not over-tighten |
| `sr2` | Empower: `-0.257` to `50825.0`; Kissel: `NULL` | Reflected/outgoing shortwave | Mostly near-zero low end but severe high artifact exists | Keep outgoing/reflected treatment permissive; raw max should not define physical upper bound |

## Clearly Broken / Not Suitable for Direct Physical Thresholding

These ranges are dominated by obvious parsing/scaling artifacts and should not be used directly to set physical upper limits.

| Field | Observed Raw Range | Assessment |
|---|---|---|
| `air_temp_1` (Empower) | `-29.54` to `48759150000.0` | Severe scaling artifact in upper bound |
| `soil_moisture` (Empower) | `0.0` to `60605.0` | Severe scaling artifact |
| `soil_temp_1` (Empower) | `-0.317` to `22758.002` | Severe scaling artifact |
| `soil_temp_2` (Empower) | `-125050.008` to `26.261` | Severe negative artifact |
| `temperature` (Empower) | `-45507.766` to `38.91` | Severe negative artifact |
| `air_pressure` (Empower) | `0.0` to `1070940.0` | Severe scaling artifact |
| `sr2` (Empower) | `-0.257` to `50825.0` | Severe high artifact |
| `air_humidity_1` (Kissel) | `14.8` to `129.4` | Over-100 RH values show sensor or parsing issues |
| `soil_temp_1` (Kissel) | `-3.22` to `55.79` | Slightly above plausible environmental bound |

## High-Signal Takeaways

1. Greenroof raw data contains substantial outliers, especially in Empower channels.
2. Kissel is structurally cleaner but has missing fields and a few values outside physical bounds.
3. Standard QC thresholds for temperature, humidity, wind, and soil moisture remain appropriate and necessary.
4. `IR1` is again the key special case: raw values are mostly negative in Empower, so a strict incoming lower bound like `>= -5` is too aggressive unless sign convention is normalized first.
5. `SR1` looks much more compatible with a near-zero lower bound than `IR1` does.
6. Outgoing channels (`IR2`, `SR2`) should remain permissive because raw sign/range behavior does not yet support tight filtering.

## Recommended Immediate QC Strategy

1. Keep standard physical ranges for air temperature, humidity, wind, soil moisture, and pressure.
2. Keep `SR1` near-zero lower bound, but allow realistic daytime highs.
3. Revisit `IR1` separately: either normalize sign first or temporarily relax lower bound so valid records are not discarded.
4. Keep outgoing radiation bounds permissive for `IR2` and `SR2`.
5. Do not use raw Empower maxima/minima directly as physical justifications; many are clearly scaled or corrupted values.

## Cross-Site Alignment Summary

Compared with parkplatz:

1. Both sites support strict QC for temperature, humidity, wind, and soil moisture.
2. Both sites show `IR1` as the problematic incoming channel for current sign/encoding assumptions.
3. Both sites support permissive treatment of outgoing radiation.
4. Greenroof `SR1` looks more physically interpretable than parkplatz `SR1`, which is more heavily affected by scaling artifacts.