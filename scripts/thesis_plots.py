"""Generate thesis diagnostic plots from synchronized_data_filtered.

Outputs:
- outputs/ET_vs_temp_signal.png
- outputs/albedo_comparison.png
- outputs/heatmap_year_season_temp_signal.png
"""

from pathlib import Path
import sys

# Allow direct execution: `python scripts/thesis_plots.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from dashboard.analysis import BingenGreenRoofAnalyzer, DataLoadError


def _load_with_chunk_fallback(analyzer: BingenGreenRoofAnalyzer) -> pd.DataFrame:
    """Load data with progressive fallback to smaller time windows."""
    try:
        analyzer.load_data()
        return analyzer.df
    except DataLoadError as exc:
        print(f"Full-table load failed: {exc}")

    years = analyzer.get_available_years()
    if not years:
        raise DataLoadError(
            "Unable to discover available years for chunked fallback."
        )

    collected = []
    failed_years = []

    for year in years:
        try:
            analyzer.load_data(year=year)
            if analyzer.df is not None and not analyzer.df.empty:
                collected.append(analyzer.df.copy())
            continue
        except DataLoadError:
            pass

        year_collected = []
        for month in range(1, 13):
            start_ts = pd.Timestamp(year=year, month=month, day=1)
            end_ts = (start_ts + pd.DateOffset(months=1)) - pd.Timedelta(microseconds=1)
            try:
                analyzer.load_data(start_ts=start_ts, end_ts=end_ts)
                if analyzer.df is not None and not analyzer.df.empty:
                    year_collected.append(analyzer.df.copy())
            except DataLoadError:
                continue

        if year_collected:
            year_df = pd.concat(year_collected).sort_index()
            year_df = year_df[~year_df.index.duplicated(keep='first')]
            collected.append(year_df)
        else:
            failed_years.append(year)

    if not collected:
        raise DataLoadError(
            "All fallback loads failed. Query windows still hit unreadable PostgreSQL blocks."
        )

    merged = pd.concat(collected).sort_index()
    merged = merged[~merged.index.duplicated(keep='first')]
    analyzer.df = merged

    if failed_years:
        print(f"Skipped unreadable year(s): {failed_years}")

    return analyzer.df


if __name__ == '__main__':
    analyzer = BingenGreenRoofAnalyzer()
    _load_with_chunk_fallback(analyzer)

    if analyzer.df is None or analyzer.df.empty:
        raise SystemExit('No data available in synchronized_data_filtered.')

    out_dir = Path('outputs')
    out_dir.mkdir(exist_ok=True)

    df = analyzer.df.copy()
    dual = df[df['has_dual_level_greenroof'] == True].dropna(subset=['delta_rh_roof', 'temp_diff_1'])

    # 1) ET proxy scatter (dual-level only)
    if not dual.empty:
        sample = dual.sample(min(len(dual), 50000), random_state=42)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(sample['delta_rh_roof'], sample['temp_diff_1'], alpha=0.15, s=4, color='steelblue')
        ax.axhline(0, color='red', linestyle='--', linewidth=1)
        ax.set_xlabel('Delta RH roof (50cm - 2m)')
        ax.set_ylabel('Temperature signal (roof - parking, degC)')
        ax.set_title('ET diagnostic (dual-level only): Delta RH vs temp signal')
        plt.tight_layout()
        plt.savefig(out_dir / 'ET_vs_temp_signal.png', dpi=150)
        plt.close(fig)

    # 2) Albedo comparison over time (monthly)
    monthly = df.groupby([df.index.year.rename('year'), df.index.month.rename('month')]).agg(
        albedo_greenroof=('albedo_greenroof', 'mean'),
        albedo_parkplatz=('albedo_parkplatz', 'mean'),
    ).reset_index()
    monthly['month_label'] = monthly['year'].astype(str) + '-' + monthly['month'].astype(str).str.zfill(2)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(monthly['month_label'], monthly['albedo_greenroof'], label='Greenroof', color='forestgreen')
    ax.plot(monthly['month_label'], monthly['albedo_parkplatz'], label='Parkplatz', color='royalblue')
    ax.set_ylabel('Albedo')
    ax.set_title('Monthly albedo comparison')
    ax.tick_params(axis='x', rotation=60)
    ax.legend()
    plt.tight_layout()
    plt.savefig(out_dir / 'albedo_comparison.png', dpi=150)
    plt.close(fig)

    # 3) Year x season heatmap for temp signal
    heat = df.groupby(['year', 'season'])['temp_diff_1'].mean().reset_index()
    season_order = ['Winter', 'Spring', 'Summer', 'Autumn']
    heat['season'] = pd.Categorical(heat['season'], categories=season_order, ordered=True)
    pivot = heat.pivot(index='year', columns='season', values='temp_diff_1').sort_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(pivot, annot=True, fmt='.2f', cmap='coolwarm', center=0, ax=ax)
    ax.set_title('Mean roof-parking temperature signal by year and season')
    plt.tight_layout()
    plt.savefig(out_dir / 'heatmap_year_season_temp_signal.png', dpi=150)
    plt.close(fig)

    print('Saved thesis figures to outputs/.')
