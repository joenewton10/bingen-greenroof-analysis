"""
Bingen Green Roof Analysis Dashboard
Streamlit app for comprehensive green roof cooling analysis.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# Import local analysis module
from analysis import BingenGreenRoofAnalyzer, CONDITION_COLORS


# Page configuration
st.set_page_config(
    page_title="Bingen Green Roof Analysis",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E7D32;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_analyzer():
    """Load and cache the analyzer with data."""
    analyzer = BingenGreenRoofAnalyzer()
    analyzer.load_data()
    analyzer.create_condition_categories()
    return analyzer


def main():
    # Header
    st.markdown('<p class="main-header">🌿 Bingen Green Roof Cooling Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Comprehensive analysis of green roof thermal performance</p>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading data from database..."):
        analyzer = load_analyzer()
    
    # Sidebar
    st.sidebar.title("⚙️ Analysis Settings")
    
    temp_diff_choice = st.sidebar.radio(
        "Temperature Difference Metric",
        ["temp_diff_2", "temp_diff_1"],
        help="temp_diff_1: Greenroof - Parkplatz Sensor 1\ntemp_diff_2: Greenroof - Parkplatz Sensor 2"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Dataset Info")
    info = analyzer.analysis_results['dataset_info']
    st.sidebar.write(f"**Records:** {info['total_measurements']:,}")
    st.sidebar.write(f"**Date Range:** {info['date_range']}")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📐 Thresholds")
    st.sidebar.markdown("""
    - **Meaningful Cooling:** < -0.2°C
    - **Strong Cooling:** < -1.2°C  
    - **Within Error:** ±0.2°C
    - **Meaningful Warming:** > +0.2°C
    """)
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Cooling Effectiveness",
        "📦 Distribution Analysis", 
        "📈 Cooling Frequency",
        "🎯 Performance Matrix",
        "🍂 Seasonal Analysis",
        "⚡ Energy Balance"
    ])
    
    # =========================================================================
    # TAB 1: Cooling Effectiveness Bar Chart
    # =========================================================================
    with tab1:
        st.header("Cooling Effectiveness by Environmental Condition")
        st.markdown(f"Using **{temp_diff_choice}** for temperature difference calculations")
        
        cooling_stats = analyzer.get_cooling_by_condition(temp_diff_choice)
        
        if not cooling_stats.empty:
            # Create bar chart
            fig = go.Figure()
            
            colors = [CONDITION_COLORS.get(c, '#808080') for c in cooling_stats['condition']]
            
            fig.add_trace(go.Bar(
                y=cooling_stats['condition'],
                x=cooling_stats['mean_effect'],
                orientation='h',
                marker_color=colors,
                error_x=dict(type='data', array=cooling_stats['std_effect'], visible=True),
                text=[f"n={n:,}" for n in cooling_stats['count']],
                textposition='outside',
                hovertemplate="<b>%{y}</b><br>Mean: %{x:.3f}°C<br>Std: %{error_x.array:.3f}°C<extra></extra>"
            ))
            
            fig.add_vline(x=0, line_dash="dash", line_color="red", line_width=2)
            fig.add_vline(x=-0.2, line_dash="dot", line_color="blue", line_width=1, 
                         annotation_text="Meaningful cooling", annotation_position="top")
            
            fig.update_layout(
                title=f"Green Roof Cooling Effectiveness ({temp_diff_choice})",
                xaxis_title="Temperature Difference [°C]",
                yaxis_title="Environmental Condition",
                height=max(500, len(cooling_stats) * 40),
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Summary table
            st.subheader("📋 Summary Statistics")
            display_df = cooling_stats[['condition', 'mean_effect', 'std_effect', 'count', 'classification']].copy()
            display_df.columns = ['Condition', 'Mean Effect (°C)', 'Std Dev (°C)', 'Sample Size', 'Classification']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # =========================================================================
    # TAB 2: Distribution Box Plots
    # =========================================================================
    with tab2:
        st.header("Distribution of Cooling Effects")
        
        dist_data = analyzer.get_condition_distribution_data(temp_diff_choice)
        
        if not dist_data.empty:
            # Order by mean
            order = dist_data.groupby('enhanced_condition')[temp_diff_choice].mean().sort_values().index.tolist()
            
            fig = px.box(
                dist_data,
                x=temp_diff_choice,
                y='enhanced_condition',
                category_orders={'enhanced_condition': order},
                color='enhanced_condition',
                color_discrete_map=CONDITION_COLORS,
                title=f"Distribution of Temperature Differences by Condition ({temp_diff_choice})"
            )
            
            fig.add_vline(x=0, line_dash="dash", line_color="red", line_width=2)
            fig.add_vline(x=-0.2, line_dash="dot", line_color="blue", line_width=1)
            fig.add_vline(x=0.2, line_dash="dot", line_color="orange", line_width=1)
            
            fig.update_layout(
                xaxis_title="Temperature Difference [°C]",
                yaxis_title="Environmental Condition",
                height=max(500, len(order) * 45),
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("**Interpretation:** Box plots show median (line), interquartile range (box), and outliers. Red dashed line = 0°C (no difference). Blue/orange dotted lines = ±0.2°C (instrument uncertainty).")
    
    # =========================================================================
    # TAB 3: Cooling Frequency Analysis
    # =========================================================================
    with tab3:
        st.header("Cooling Frequency Analysis")
        st.markdown("How often does meaningful cooling occur under each condition?")
        
        cooling_stats = analyzer.get_cooling_by_condition(temp_diff_choice)
        
        if not cooling_stats.empty:
            # Prepare data for grouped bar chart
            freq_data = []
            for _, row in cooling_stats.iterrows():
                freq_data.append({'Condition': row['condition'], 'Category': 'Meaningful Cooling (<-0.2°C)', 'Frequency': row['meaningful_cooling_pct']})
                freq_data.append({'Condition': row['condition'], 'Category': 'Strong Cooling (<-1.2°C)', 'Frequency': row['strong_cooling_pct']})
                freq_data.append({'Condition': row['condition'], 'Category': 'Within Error (±0.2°C)', 'Frequency': row['within_error_pct']})
                freq_data.append({'Condition': row['condition'], 'Category': 'Meaningful Warming (>0.2°C)', 'Frequency': row['meaningful_warming_pct']})
            
            freq_df = pd.DataFrame(freq_data)
            
            fig = px.bar(
                freq_df,
                y='Condition',
                x='Frequency',
                color='Category',
                orientation='h',
                barmode='group',
                color_discrete_map={
                    'Meaningful Cooling (<-0.2°C)': '#2196F3',
                    'Strong Cooling (<-1.2°C)': '#009688',
                    'Within Error (±0.2°C)': '#FFC107',
                    'Meaningful Warming (>0.2°C)': '#F44336'
                },
                title="Cooling Frequency by Environmental Condition"
            )
            
            fig.update_layout(
                xaxis_title="Frequency (%)",
                yaxis_title="Environmental Condition",
                height=max(500, len(cooling_stats) * 50),
                legend_title="Category"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Frequency table
            st.subheader("📋 Frequency Table")
            freq_table = cooling_stats[['condition', 'meaningful_cooling_pct', 'strong_cooling_pct', 
                                        'within_error_pct', 'meaningful_warming_pct', 'count']].copy()
            freq_table.columns = ['Condition', 'Meaningful Cooling %', 'Strong Cooling %', 
                                  'Within Error %', 'Meaningful Warming %', 'Sample Size']
            st.dataframe(freq_table, use_container_width=True, hide_index=True)
    
    # =========================================================================
    # TAB 4: Performance Matrix
    # =========================================================================
    with tab4:
        st.header("Performance Matrix")
        st.markdown("Comparing mean cooling effect vs. cooling frequency")
        
        cooling_stats = analyzer.get_cooling_by_condition(temp_diff_choice)
        
        if not cooling_stats.empty:
            fig = go.Figure()
            
            colors = [CONDITION_COLORS.get(c, '#808080') for c in cooling_stats['condition']]
            
            fig.add_trace(go.Scatter(
                x=cooling_stats['mean_effect'],
                y=cooling_stats['meaningful_cooling_pct'],
                mode='markers+text',
                marker=dict(size=15, color=colors, line=dict(width=2, color='black')),
                text=cooling_stats['condition'],
                textposition='top center',
                textfont=dict(size=9),
                hovertemplate="<b>%{text}</b><br>Mean Effect: %{x:.3f}°C<br>Cooling Freq: %{y:.1f}%<extra></extra>"
            ))
            
            # Reference lines
            fig.add_vline(x=-0.2, line_dash="dash", line_color="red", line_width=2,
                         annotation_text="Meaningful cooling threshold")
            fig.add_hline(y=50, line_dash="dash", line_color="blue", line_width=2,
                         annotation_text="50% frequency")
            
            # Quadrant labels
            fig.add_annotation(x=-1.5, y=80, text="✅ Excellent<br>Performance", 
                             showarrow=False, font=dict(size=12, color="green"))
            fig.add_annotation(x=0.5, y=20, text="❌ Poor<br>Performance", 
                             showarrow=False, font=dict(size=12, color="red"))
            
            fig.update_layout(
                title=f"Performance Matrix: Cooling Effect vs. Frequency ({temp_diff_choice})",
                xaxis_title="Mean Cooling Effect [°C]",
                yaxis_title="Meaningful Cooling Frequency (%)",
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("""
            **Interpretation:**
            - **Top-left quadrant:** Best performance (strong cooling, high frequency)
            - **Bottom-right quadrant:** Worst performance (warming, low cooling frequency)
            - Red dashed line: -0.2°C threshold for meaningful cooling
            - Blue dashed line: 50% frequency threshold
            """)
    
    # =========================================================================
    # TAB 5: Seasonal Analysis
    # =========================================================================
    with tab5:
        st.header("Seasonal Variation in Stress Conditions")
        
        seasonal_data = analyzer.get_seasonal_stress_data(temp_diff_choice)
        
        if not seasonal_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = px.bar(
                    seasonal_data,
                    x='season',
                    y='mean_effect',
                    color='condition',
                    barmode='group',
                    color_discrete_map=CONDITION_COLORS,
                    title="Mean Cooling Effect by Season"
                )
                fig1.add_hline(y=0, line_dash="dash", line_color="red")
                fig1.add_hline(y=-0.2, line_dash="dot", line_color="orange")
                fig1.update_layout(
                    xaxis_title="Season",
                    yaxis_title="Mean Cooling Effect [°C]",
                    height=450
                )
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = px.bar(
                    seasonal_data,
                    x='season',
                    y='meaningful_cooling_pct',
                    color='condition',
                    barmode='group',
                    color_discrete_map=CONDITION_COLORS,
                    title="Meaningful Cooling Frequency by Season"
                )
                fig2.update_layout(
                    xaxis_title="Season",
                    yaxis_title="Meaningful Cooling Frequency (%)",
                    height=450
                )
                st.plotly_chart(fig2, use_container_width=True)
            
            # Seasonal summary table
            st.subheader("📋 Seasonal Summary")
            st.dataframe(seasonal_data, use_container_width=True, hide_index=True)
        else:
            st.warning("Insufficient data for seasonal stress condition analysis.")
    
    # =========================================================================
    # TAB 6: Energy Balance Analysis (NEW)
    # =========================================================================
    with tab6:
        st.header("⚡ Energy Balance Analysis")
        st.markdown("""
        This analysis explores **why warming occurs instead of cooling** by examining the 
        energy fluxes at the parkplatz (reference) site throughout the day.
        """)
        
        # Get hourly data
        hourly = analyzer.get_hourly_energy_analysis()
        
        # Chart 1: Hourly Energy Pattern with Temperature Difference
        st.subheader("1️⃣ Hourly Energy Pattern vs Temperature Difference")
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Energy traces (right y-axis)
        fig.add_trace(
            go.Scatter(x=hourly['hour'], y=hourly['energy_from_air_parkplatz'],
                      name="Energy from Air (IR1 + σεT⁴)", line=dict(color='#FF6B6B', width=2)),
            secondary_y=True
        )
        fig.add_trace(
            go.Scatter(x=hourly['hour'], y=hourly['energy_from_surface_parkplatz'],
                      name="Energy from Surface (IR2 + σεT⁴)", line=dict(color='#4ECDC4', width=2)),
            secondary_y=True
        )
        fig.add_trace(
            go.Scatter(x=hourly['hour'], y=hourly['radiation_balance_parkplatz'],
                      name="Net Radiation Balance", line=dict(color='#45B7D1', width=2, dash='dash')),
            secondary_y=True
        )
        fig.add_trace(
            go.Scatter(x=hourly['hour'], y=hourly['avg_global_radiation_greenroof'],
                      name="Global Radiation (Greenroof)", line=dict(color='#FFE66D', width=2)),
            secondary_y=True
        )
        
        # Temperature difference traces (left y-axis)
        fig.add_trace(
            go.Scatter(x=hourly['hour'], y=hourly['temp_diff_1'],
                      name="temp_diff_1", line=dict(color='#2E7D32', width=3)),
            secondary_y=False
        )
        fig.add_trace(
            go.Scatter(x=hourly['hour'], y=hourly['temp_diff_2'],
                      name="temp_diff_2", line=dict(color='#1565C0', width=3)),
            secondary_y=False
        )
        
        # Add zero line for temp diff
        fig.add_hline(y=0, line_dash="dash", line_color="red", line_width=1, secondary_y=False)
        
        fig.update_layout(
            title="Hourly Energy Fluxes and Temperature Differences",
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
        )
        fig.update_xaxes(title_text="Hour of Day", dtick=2)
        fig.update_yaxes(title_text="Temperature Difference [°C]", secondary_y=False)
        fig.update_yaxes(title_text="Energy Flux [W/m²]", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("""
        **Key Observations:**
        - When **radiation balance** is high (midday), there's more energy input → potential warming
        - When **radiation balance** is low/negative (night), energy is lost → potential cooling
        - **temp_diff > 0** means greenroof is warmer than parkplatz
        - **temp_diff < 0** means greenroof is cooler (desired cooling effect)
        """)
        
        # Chart 2: Correlation scatter
        st.subheader("2️⃣ Radiation Balance vs Temperature Difference")
        
        corr_data = analyzer.get_radiation_vs_tempdiff_correlation()
        
        # Sample for performance (max 10000 points)
        if len(corr_data) > 10000:
            sample_data = corr_data.sample(n=10000, random_state=42)
        else:
            sample_data = corr_data
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_scatter1 = px.scatter(
                sample_data,
                x='radiation_balance_parkplatz',
                y=temp_diff_choice,
                opacity=0.3,
                color_discrete_sequence=['#2196F3'],
                title=f"Radiation Balance vs {temp_diff_choice}"
            )
            fig_scatter1.add_hline(y=0, line_dash="dash", line_color="red")
            fig_scatter1.add_vline(x=0, line_dash="dash", line_color="gray")
            fig_scatter1.update_layout(
                xaxis_title="Radiation Balance [W/m²]",
                yaxis_title=f"{temp_diff_choice} [°C]",
                height=400
            )
            st.plotly_chart(fig_scatter1, use_container_width=True)
        
        with col2:
            # Calculate correlation
            corr = corr_data['radiation_balance_parkplatz'].corr(corr_data[temp_diff_choice])
            
            # Binned averages
            corr_data['rad_bin'] = pd.cut(corr_data['radiation_balance_parkplatz'], bins=20)
            binned = corr_data.groupby('rad_bin')[temp_diff_choice].mean().reset_index()
            binned['rad_mid'] = binned['rad_bin'].apply(lambda x: x.mid if pd.notna(x) else np.nan)
            binned = binned.dropna()
            
            fig_trend = px.line(
                binned,
                x='rad_mid',
                y=temp_diff_choice,
                markers=True,
                title=f"Trend: Binned Radiation vs {temp_diff_choice}"
            )
            fig_trend.add_hline(y=0, line_dash="dash", line_color="red")
            fig_trend.update_layout(
                xaxis_title="Radiation Balance [W/m²]",
                yaxis_title=f"Mean {temp_diff_choice} [°C]",
                height=400
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        
        st.metric("Correlation Coefficient", f"{corr:.3f}")
        
        # Chart 3: Seasonal energy patterns
        st.subheader("3️⃣ Seasonal Energy Patterns")
        
        seasonal = analyzer.get_seasonal_energy_analysis()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_seasonal_energy = px.bar(
                seasonal,
                x='season',
                y=['energy_from_air_parkplatz', 'energy_from_surface_parkplatz', 'radiation_balance_parkplatz'],
                barmode='group',
                title="Seasonal Energy Fluxes",
                labels={'value': 'Energy [W/m²]', 'variable': 'Flux Type'}
            )
            fig_seasonal_energy.update_layout(height=400)
            st.plotly_chart(fig_seasonal_energy, use_container_width=True)
        
        with col2:
            fig_seasonal_temp = px.bar(
                seasonal,
                x='season',
                y=['temp_diff_1', 'temp_diff_2'],
                barmode='group',
                title="Seasonal Temperature Differences",
                color_discrete_map={'temp_diff_1': '#2E7D32', 'temp_diff_2': '#1565C0'}
            )
            fig_seasonal_temp.add_hline(y=0, line_dash="dash", line_color="red")
            fig_seasonal_temp.update_layout(
                yaxis_title="Temperature Difference [°C]",
                height=400
            )
            st.plotly_chart(fig_seasonal_temp, use_container_width=True)
        
        # Explanation box
        st.markdown("---")
        st.subheader("🔍 Why is Warming Occurring?")
        
        avg_td1 = analyzer.df['temp_diff_1'].mean()
        avg_td2 = analyzer.df['temp_diff_2'].mean()
        avg_rad = analyzer.df['radiation_balance_parkplatz'].mean()
        
        st.markdown(f"""
        **Overall Averages:**
        - Mean temp_diff_1: **{avg_td1:.3f}°C** (Greenroof {'warmer' if avg_td1 > 0 else 'cooler'} than Parkplatz Sensor 1)
        - Mean temp_diff_2: **{avg_td2:.3f}°C** (Greenroof {'warmer' if avg_td2 > 0 else 'cooler'} than Parkplatz Sensor 2)
        - Mean Radiation Balance: **{avg_rad:.1f} W/m²**
        
        **Possible Explanations for Warming:**
        1. **Daytime solar gain dominates:** High radiation balance during day causes warming that outweighs nighttime cooling
        2. **Thermal mass effect:** Green roof substrate retains heat longer
        3. **Reduced convective cooling:** Vegetation may trap air, reducing wind-driven heat loss
        4. **Sensor placement differences:** Location differences between greenroof and parkplatz sensors
        5. **Evapotranspiration limited:** Low soil moisture reduces evaporative cooling effect
        
        **Next steps:** Filter by time of day, season, or soil moisture to identify when cooling actually occurs.
        """)


if __name__ == "__main__":
    main()
