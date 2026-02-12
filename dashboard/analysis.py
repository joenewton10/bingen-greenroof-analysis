"""
Bingen Green Roof Analysis Module
Adapted from enhanced_complexindex_temp_diff_2.py for the Bingen pipeline.
Connects to Bingen_Greenroof_DB and uses synchronized_data_filtered table.
"""

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import warnings

try:
    import streamlit as st
except Exception:
    st = None
warnings.filterwarnings('ignore')


def _get_secret(name):
    if st is not None and hasattr(st, "secrets") and name in st.secrets:
        return st.secrets[name]
    return os.getenv(name)


def _get_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_db_params():
    return {
        "dbname": _get_secret("DB_NAME") or "Bingen_Greenroof_DB",
        "user": _get_secret("DB_USER") or "postgres",
        "password": _get_secret("DB_PASSWORD") or "",
        "host": _get_secret("DB_HOST") or "localhost",
        "port": _get_int(_get_secret("DB_PORT"), 5432),
    }


class BingenGreenRoofAnalyzer:
    """
    Green Roof Analysis for Bingen Pipeline.
    Uses temp_diff_1/temp_diff_2 and energy columns from synchronized_data_filtered.
    """
    
    def __init__(self, db_params=None):
        defaults = _default_db_params()
        if db_params:
            defaults.update({key: value for key, value in db_params.items() if value is not None})
        self.db_params = defaults
            
        self.df = None
        self.analysis_results = {}
        
    def load_data(self):
        """Load data from Bingen pipeline synchronized_data_filtered table."""
        engine = create_engine(
            f"postgresql://{self.db_params['user']}:{self.db_params['password']}@"
            f"{self.db_params['host']}:{self.db_params['port']}/{self.db_params['dbname']}"
        )
        
        query = """
        SELECT 
            timestamp,
            avg_air_temperature_greenroof,
            avg_air_temp_1_parkplatz,
            avg_air_temp_2_parkplatz,
            avg_relative_humidity_greenroof,
            avg_wind_speed_greenroof,
            avg_soil_temperature_greenroof,
            avg_soil_moisture_greenroof,
            avg_global_radiation_greenroof,
            avg_ir1_parkplatz,
            avg_ir2_parkplatz,
            avg_sr1_parkplatz,
            avg_sr2_parkplatz,
            avg_temp_parkplatz,
            temp_diff_1,
            temp_diff_2,
            energy_from_air_parkplatz,
            energy_from_surface_parkplatz,
            radiation_balance_parkplatz
        FROM synchronized_data_filtered 
        WHERE temp_diff_1 IS NOT NULL 
          AND temp_diff_2 IS NOT NULL
        ORDER BY timestamp;
        """
        
        self.df = pd.read_sql_query(query, engine)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df.set_index('timestamp', inplace=True)
        self.df = self.df.sort_index()
        self.df = self.df[~self.df.index.duplicated(keep='first')]
        
        # Add time features
        self.df['hour'] = self.df.index.hour
        self.df['month'] = self.df.index.month
        self.df['season'] = self.df['month'].map({
            12: 'Winter', 1: 'Winter', 2: 'Winter',
            3: 'Spring', 4: 'Spring', 5: 'Spring',
            6: 'Summer', 7: 'Summer', 8: 'Summer',
            9: 'Autumn', 10: 'Autumn', 11: 'Autumn'
        })
        
        self.analysis_results['dataset_info'] = {
            'total_measurements': len(self.df),
            'date_range': f"{self.df.index.min().strftime('%Y-%m-%d')} to {self.df.index.max().strftime('%Y-%m-%d')}",
        }
        
        return self.df
    
    def get_hourly_energy_analysis(self):
        """Get hourly averages for energy balance analysis."""
        hourly = self.df.groupby('hour').agg({
            'temp_diff_1': 'mean',
            'temp_diff_2': 'mean',
            'energy_from_air_parkplatz': 'mean',
            'energy_from_surface_parkplatz': 'mean',
            'radiation_balance_parkplatz': 'mean',
            'avg_global_radiation_greenroof': 'mean',
        }).reset_index()
        
        return hourly
    
    def get_seasonal_energy_analysis(self):
        """Get seasonal averages for energy balance."""
        seasonal = self.df.groupby('season').agg({
            'temp_diff_1': 'mean',
            'temp_diff_2': 'mean',
            'energy_from_air_parkplatz': 'mean',
            'energy_from_surface_parkplatz': 'mean',
            'radiation_balance_parkplatz': 'mean',
            'avg_global_radiation_greenroof': 'mean',
        }).reset_index()
        
        # Sort seasons properly
        season_order = ['Winter', 'Spring', 'Summer', 'Autumn']
        seasonal['season'] = pd.Categorical(seasonal['season'], categories=season_order, ordered=True)
        seasonal = seasonal.sort_values('season')
        
        return seasonal
    
    def get_radiation_vs_tempdiff_correlation(self):
        """Get data for radiation vs temperature difference correlation."""
        return self.df[['radiation_balance_parkplatz', 'temp_diff_1', 'temp_diff_2', 
                        'energy_from_air_parkplatz', 'energy_from_surface_parkplatz']].dropna()
    
    def categorize_weather_variable(self, value, variable_type):
        """Categorize weather variables using scientific thresholds."""
        if pd.isna(value):
            return 'Unknown'
        
        thresholds = {
            'air_temperature': {
                'low_max_exclusive': 5.0,
                'medium_max_exclusive': 30.0,
                'categories': ['Dormant / Cold', 'Growth / Comfort', 'Heat Stress']
            },
            'wind_speed': {
                'low_max_exclusive': 1.5,
                'medium_max_exclusive': 5.0,
                'categories': ['Calm Wind', 'Moderate Wind', 'High Wind']
            },
            'solar_radiation': {
                'low_max_exclusive': 200,
                'medium_max_exclusive': 600,
                'categories': ['Overcast', 'Partly Cloudy', 'Clear Sky']
            },
            'soil_vwc': {
                'low_max_exclusive': 13,
                'medium_max_exclusive': 33,
                'categories': ['Wilt Risk', 'Optimal', 'Saturation']
            },
            'air_humidity': {
                'low_max_exclusive': 40,
                'medium_max_exclusive': 60,
                'categories': ['Dry', 'Optimal', 'Humid']
            }
        }
        
        if variable_type not in thresholds:
            return 'Unknown'
        
        thresh = thresholds[variable_type]
        if value < thresh['low_max_exclusive']:
            return thresh['categories'][0]
        elif value < thresh['medium_max_exclusive']:
            return thresh['categories'][1]
        else:
            return thresh['categories'][2]
    
    def create_condition_categories(self):
        """Create enhanced condition categories."""
        
        def classify_condition(row):
            temp = row['avg_air_temperature_greenroof']
            humidity = row.get('avg_relative_humidity_greenroof', np.nan)
            wind = row.get('avg_wind_speed_greenroof', np.nan)
            solar = row.get('avg_global_radiation_greenroof', np.nan)
            soil = row.get('avg_soil_moisture_greenroof', np.nan)
            
            temp_cat = self.categorize_weather_variable(temp, 'air_temperature')
            humidity_cat = self.categorize_weather_variable(humidity, 'air_humidity')
            wind_cat = self.categorize_weather_variable(wind, 'wind_speed')
            solar_cat = self.categorize_weather_variable(solar, 'solar_radiation')
            soil_cat = self.categorize_weather_variable(soil, 'soil_vwc')
            
            # Compound stress conditions
            if temp_cat == 'Heat Stress' and solar_cat == 'Clear Sky' and soil_cat == 'Wilt Risk':
                return 'Compound Triple Stress'
            elif temp_cat == 'Heat Stress' and solar_cat == 'Clear Sky' and humidity_cat == 'Dry':
                return 'High ET Stress'
            elif temp_cat == 'Heat Stress' and wind_cat == 'Calm Wind' and humidity_cat == 'Dry':
                return 'Urban Heat Island'
            elif temp_cat == 'Heat Stress' and solar_cat == 'Clear Sky' and wind_cat == 'Calm Wind':
                return 'Extreme Heat Stress'
            elif temp_cat == 'Heat Stress' and wind_cat == 'High Wind':
                return 'Heat Stress + High Wind'
            elif temp_cat == 'Heat Stress' and soil_cat == 'Wilt Risk':
                return 'Drought Stress'
            elif temp_cat == 'Growth / Comfort' and soil_cat == 'Optimal' and solar_cat == 'Partly Cloudy':
                return 'Optimal Growth'
            elif temp_cat == 'Dormant / Cold' and wind_cat == 'High Wind':
                return 'Cold + Wind Stress'
            elif solar_cat == 'Clear Sky' and wind_cat == 'Calm Wind' and temp_cat == 'Growth / Comfort':
                return 'High Solar + Calm'
            elif soil_cat == 'Saturation' and temp_cat == 'Growth / Comfort':
                return 'Saturated Growth'
            elif humidity_cat == 'Humid' and temp_cat == 'Growth / Comfort':
                return 'High Humidity Growth'
            else:
                return temp_cat
        
        self.df['enhanced_condition'] = self.df.apply(classify_condition, axis=1)
        
        return self.df['enhanced_condition'].value_counts()
    
    def get_cooling_by_condition(self, temp_diff_col='temp_diff_2'):
        """Get cooling statistics by enhanced condition."""
        if 'enhanced_condition' not in self.df.columns:
            self.create_condition_categories()
        
        stats = []
        for condition in self.df['enhanced_condition'].unique():
            cat_data = self.df[self.df['enhanced_condition'] == condition]
            if len(cat_data) >= 30:
                mean_effect = cat_data[temp_diff_col].mean()
                std_effect = cat_data[temp_diff_col].std()
                count = len(cat_data)
                
                # Cooling frequencies
                meaningful_cooling = (cat_data[temp_diff_col] < -0.2).sum() / count * 100
                strong_cooling = (cat_data[temp_diff_col] < -1.2).sum() / count * 100
                within_error = ((cat_data[temp_diff_col] >= -0.2) & (cat_data[temp_diff_col] <= 0.2)).sum() / count * 100
                meaningful_warming = (cat_data[temp_diff_col] > 0.2).sum() / count * 100
                
                # Classification
                if mean_effect < -1.2:
                    effect_class = 'Very Strong Cooling'
                elif mean_effect < -0.4:
                    effect_class = 'Strong Cooling'
                elif mean_effect < -0.2:
                    effect_class = 'Moderate Cooling'
                elif -0.2 <= mean_effect <= 0.2:
                    effect_class = 'Within Instrument Error'
                elif mean_effect <= 0.4:
                    effect_class = 'Weak Warming'
                else:
                    effect_class = 'Strong Warming'
                
                stats.append({
                    'condition': condition,
                    'mean_effect': round(mean_effect, 3),
                    'std_effect': round(std_effect, 3),
                    'count': count,
                    'meaningful_cooling_pct': round(meaningful_cooling, 1),
                    'strong_cooling_pct': round(strong_cooling, 1),
                    'within_error_pct': round(within_error, 1),
                    'meaningful_warming_pct': round(meaningful_warming, 1),
                    'classification': effect_class
                })
        
        return pd.DataFrame(stats).sort_values('mean_effect')
    
    def get_condition_distribution_data(self, temp_diff_col='temp_diff_2'):
        """Get data for box plot distribution by condition."""
        if 'enhanced_condition' not in self.df.columns:
            self.create_condition_categories()
        
        # Filter to conditions with enough data
        valid_conditions = self.df['enhanced_condition'].value_counts()
        valid_conditions = valid_conditions[valid_conditions >= 30].index.tolist()
        
        return self.df[self.df['enhanced_condition'].isin(valid_conditions)][[
            'enhanced_condition', temp_diff_col, 'season', 'hour'
        ]].copy()
    
    def get_seasonal_stress_data(self, temp_diff_col='temp_diff_2'):
        """Get seasonal variation data for stress conditions."""
        if 'enhanced_condition' not in self.df.columns:
            self.create_condition_categories()
        
        stress_keywords = ['Stress', 'Compound', 'High ET', 'Urban Heat', 'Drought', 'Extreme']
        stress_conditions = [c for c in self.df['enhanced_condition'].unique() 
                           if any(kw in c for kw in stress_keywords)]
        
        seasonal_data = []
        for condition in stress_conditions:
            for season in ['Winter', 'Spring', 'Summer', 'Autumn']:
                subset = self.df[(self.df['enhanced_condition'] == condition) & 
                               (self.df['season'] == season)]
                if len(subset) >= 5:
                    mean_effect = subset[temp_diff_col].mean()
                    meaningful_cooling = (subset[temp_diff_col] < -0.2).sum() / len(subset) * 100
                    seasonal_data.append({
                        'condition': condition,
                        'season': season,
                        'mean_effect': round(mean_effect, 3),
                        'meaningful_cooling_pct': round(meaningful_cooling, 1),
                        'count': len(subset)
                    })
        
        return pd.DataFrame(seasonal_data)


# Color scheme for conditions
CONDITION_COLORS = {
    'Dormant / Cold': '#2196F3',
    'Growth / Comfort': '#4CAF50', 
    'Heat Stress': '#F44336',
    'Compound Triple Stress': '#4A0E0E',
    'High ET Stress': '#7B1FA2',
    'Urban Heat Island': '#E65100',
    'Extreme Heat Stress': '#B71C1C',
    'Heat Stress + High Wind': '#FF5722',
    'Drought Stress': '#FF9800',
    'Cold + Wind Stress': '#1976D2',
    'Optimal Growth': '#66BB6A',
    'High Solar + Calm': '#FFC107',
    'Saturated Growth': '#00BCD4',
    'High Humidity Growth': '#9C27B0',
    'Unknown': '#9E9E9E',
}
