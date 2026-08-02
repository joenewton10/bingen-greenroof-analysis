"""
One-command monthly update runner for the Bingen pipeline.

Default flow:
1) run_pipeline.py --dry-run --verbose
2) run_pipeline.py
3) verify_pipeline.py
4) build_30min_table.py

Usage:
    python scripts/run_monthly_update.py

Optional flags:
    --skip-dry-run        Skip the dry-run precheck
    --skip-30min          Skip 30-minute table build
    --continue-on-30min-error
                          Continue even if 30-minute build fails
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_step(label: str, cmd: list[str]) -> float:
    """Run one pipeline step and return elapsed seconds."""
    print("\n" + "=" * 72)
    print(f"STEP: {label}")
    print(f"CMD : {' '.join(cmd)}")
    print("=" * 72)

    t0 = time.time()
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False)
    elapsed = time.time() - t0

    if completed.returncode != 0:
        raise RuntimeError(f"Step failed ({label}) with exit code {completed.returncode}")

    print(f"[OK] {label} completed in {elapsed:.1f}s")
    return elapsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full monthly update workflow in one command."
    )
    parser.add_argument(
        "--skip-dry-run",
        action="store_true",
        help="Skip dry-run precheck",
    )
    parser.add_argument(
        "--skip-30min",
        action="store_true",
        help="Skip 30-minute aggregate table build",
    )
    parser.add_argument(
        "--continue-on-30min-error",
        action="store_true",
        help="Do not fail the run if 30-minute table build fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python_exe = sys.executable

    print("=" * 72)
    print("BINGEN GREENROOF - MONTHLY UPDATE RUNNER")
    print("=" * 72)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Python       : {python_exe}")

    timings: list[tuple[str, float]] = []

    try:
        if not args.skip_dry_run:
            timings.append((
                "dry-run",
                _run_step(
                    "Pipeline dry-run",
                    [python_exe, "scripts/run_pipeline.py", "--dry-run", "--verbose"],
                ),
            ))

        timings.append((
            "pipeline",
            _run_step(
                "Full pipeline",
                [python_exe, "scripts/run_pipeline.py"],
            ),
        ))

        timings.append((
            "verify",
            _run_step(
                "Pipeline verification",
                [python_exe, "scripts/verify_pipeline.py"],
            ),
        ))

        if not args.skip_30min:
            try:
                timings.append((
                    "30min",
                    _run_step(
                        "Build 30-minute table",
                        [python_exe, "scripts/build_30min_table.py"],
                    ),
                ))
            except Exception as exc:
                if args.continue_on_30min_error:
                    print(f"[WARN] 30-minute build failed but continuing: {exc}")
                else:
                    raise

    except Exception as exc:
        print(f"\n[ERROR] Monthly update failed: {exc}")
        print("Tip: inspect latest logs in logs/ and rerun with dry-run first.")
        return 1

    total = sum(sec for _, sec in timings)
    print("\n" + "=" * 72)
    print("MONTHLY UPDATE COMPLETED")
    print("=" * 72)
    for name, sec in timings:
        print(f"{name:10s}: {sec:8.1f}s")
    print(f"total     : {total:8.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
