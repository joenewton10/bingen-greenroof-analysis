-- PostgreSQL optimization for dashboard query speed and long-term growth
-- Target table: synchronized_data_filtered

BEGIN;

-- 1) Core time index for range filters and ordering
CREATE INDEX IF NOT EXISTS idx_sync_timestamp
ON synchronized_data_filtered (timestamp);

-- 2) BRIN index for very large append-mostly time-series tables
CREATE INDEX IF NOT EXISTS idx_sync_timestamp_brin
ON synchronized_data_filtered
USING BRIN (timestamp);

-- 3) Year expression index for yearly analysis mode
CREATE INDEX IF NOT EXISTS idx_sync_year
ON synchronized_data_filtered ((EXTRACT(YEAR FROM timestamp)));

-- 4) Partial index to match dashboard filter predicate
CREATE INDEX IF NOT EXISTS idx_sync_tempdiff_notnull_ts
ON synchronized_data_filtered (timestamp)
WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL;

COMMIT;

-- Optional: materialized views for pre-aggregated dashboard queries
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sync_hourly_dashboard AS
SELECT
    date_trunc('hour', timestamp) AS hour_ts,
    EXTRACT(YEAR FROM timestamp)::int AS year,
    EXTRACT(MONTH FROM timestamp)::int AS month,
    EXTRACT(HOUR FROM timestamp)::int AS hour,
    AVG(temp_diff_1) AS temp_diff_1,
    AVG(temp_diff_2) AS temp_diff_2,
    AVG(energy_from_air_parkplatz) AS energy_from_air_parkplatz,
    AVG(energy_from_surface_parkplatz) AS energy_from_surface_parkplatz,
    AVG(radiation_balance_parkplatz) AS radiation_balance_parkplatz,
    AVG(avg_global_radiation_greenroof) AS avg_global_radiation_greenroof,
    COUNT(*) AS records
FROM synchronized_data_filtered
WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
GROUP BY 1, 2, 3, 4;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_sync_hourly_dashboard_hour_ts
ON mv_sync_hourly_dashboard (hour_ts);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sync_yearly_dashboard AS
SELECT
    EXTRACT(YEAR FROM timestamp)::int AS year,
    COUNT(*) AS records,
    AVG(temp_diff_1) AS mean_temp_diff_1,
    AVG(temp_diff_2) AS mean_temp_diff_2
FROM synchronized_data_filtered
WHERE temp_diff_1 IS NOT NULL AND temp_diff_2 IS NOT NULL
GROUP BY 1
ORDER BY 1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_sync_yearly_dashboard_year
ON mv_sync_yearly_dashboard (year);

-- Refresh after each pipeline run (or schedule via cron/pgAgent)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sync_hourly_dashboard;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sync_yearly_dashboard;

ANALYZE synchronized_data_filtered;
