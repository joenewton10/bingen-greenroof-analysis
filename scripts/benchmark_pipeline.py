"""
Benchmark harness for pipeline performance tracking.
Times each stage independently and outputs stage timings as JSON.
"""
import json
import time
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ingest.ingest_greenroof import ingest_greenroof
from pipeline.ingest.ingest_parkplatz import ingest_parkplatz
from pipeline.qc_filtering.qc_filter_greenroof import qc_filter_greenroof
from pipeline.qc_filtering.qc_filter_parkplatz import qc_filter_parkplatz
from pipeline.harmonize.harmonize_greenroof import harmonize_greenroof
from pipeline.harmonize.harmonize_parkplatz import harmonize_parkplatz
from pipeline.sync.sync_sites import sync_data
from pipeline.ingest.base import get_connection

RESULTS_DIR = PROJECT_ROOT / "logs"
RESULTS_DIR.mkdir(exist_ok=True)


def refresh_dashboard_materialized_views():
    """Refresh optional dashboard materialized views if they exist."""
    refresh_sql = [
        'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sync_hourly_dashboard;',
        'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sync_yearly_dashboard;',
    ]

    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        for sql in refresh_sql:
            try:
                cur.execute(sql)
            except Exception:
                pass
    finally:
        cur.close()
        conn.close()


def benchmark_stage(name, func):
    """Run a stage function and return (elapsed_seconds, exit_code)."""
    print(f"\n[{name}] Starting...")
    start = time.time()
    exit_code = 0
    try:
        func()
    except Exception as exc:
        print(f"[{name}] ERROR: {exc}")
        exit_code = 1
    elapsed = time.time() - start
    print(f"[{name}] Completed in {elapsed:.2f}s (exit={exit_code})")
    return elapsed, exit_code


def main():
    print("=" * 70)
    print("BINGEN GREENROOF PIPELINE - BENCHMARK MODE")
    print("=" * 70)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"benchmark_{run_id}.json"

    stages = [
        ("INGEST: Greenroof (Empower + Kissel)", ingest_greenroof),
        ("INGEST: Parkplatz", ingest_parkplatz),
        ("QC FILTER: Greenroof", qc_filter_greenroof),
        ("QC FILTER: Parkplatz", qc_filter_parkplatz),
        ("HARMONIZE: Greenroof", harmonize_greenroof),
        ("HARMONIZE: Parkplatz", harmonize_parkplatz),
        ("SYNC: Greenroof + Parkplatz", sync_data),
        ("REFRESH: Dashboard Views", refresh_dashboard_materialized_views),
    ]

    results = {
        "run_id": run_id,
        "start_time": datetime.now().isoformat(),
        "stages": [],
        "total_elapsed_seconds": 0.0,
        "overall_exit_code": 0,
    }

    pipeline_start = time.time()

    for stage_name, stage_func in stages:
        elapsed, exit_code = benchmark_stage(stage_name, stage_func)
        results["stages"].append({
            "name": stage_name,
            "elapsed_seconds": round(elapsed, 2),
            "exit_code": exit_code,
        })
        if exit_code != 0:
            results["overall_exit_code"] = 1

    total_elapsed = time.time() - pipeline_start
    results["total_elapsed_seconds"] = round(total_elapsed, 2)
    results["end_time"] = datetime.now().isoformat()

    # Write results as JSON
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Run ID: {run_id}")
    print(f"Total elapsed: {results['total_elapsed_seconds']:.2f}s")
    print(f"Overall exit code: {results['overall_exit_code']}")
    print("\nStage breakdown:")
    for stage in results["stages"]:
        status = "✓" if stage["exit_code"] == 0 else "✗"
        print(f"  {status} {stage['name']:45s} {stage['elapsed_seconds']:8.2f}s")
    print(f"\nDetailed results: {results_file}")
    print("=" * 70)

    return results["overall_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
