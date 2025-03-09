import streamlit as st
import pandas as pd
from data import (
    sync_data, fetch_data_from_db, calculate_average_metrics, 
    fetch_last_7_runs, load_goal_config, save_goal_config, 
    fetch_last_activity, calculate_volume_goal_progress, 
    calculate_performance_goal_progress, calculate_recovery_status,
    get_training_status, calculate_training_consistency,
    calculate_fatigue_score, calculate_next_milestone,
    get_recent_achievement, calculate_training_load,
    generate_quick_actions, get_weather_recommendation,
    calculate_monthly_stats, calculate_personal_bests,
    find_similar_runs, analyze_weather_impact,
    calculate_heart_rate_zones, calculate_pace_zones,
    calculate_training_metrics, calculate_fatigue_metrics,
    calculate_training_balance, analyze_performance_factors,
    generate_improvement_recommendations,
    calculate_goal_projections,
    calculate_goal_timing,
    generate_goal_based_recommendations,
)
from viz import (
    format_last_7_runs_table, format_combined_average_metrics_table, 
    create_trend_chart, format_runs_with_splits_table, 
    create_split_pace_chart, create_split_heartrate_chart,
    create_training_calendar, create_distance_distribution,
    create_time_distribution, create_long_term_trend,
    create_detailed_split_chart, create_pace_elevation_chart,
    create_runs_comparison_chart, create_heart_rate_zones_chart,
    create_pace_zones_chart, create_health_trend_chart,
    fetch_splits_from_db, create_pace_distribution
)
import os
from llm_service import GeminiService, OllamaService, create_llm_service
from datetime import datetime

def main():
    st.set_page_config(layout="wide")
    st.title("AI Running Coach")

    # Initialize or load the user's goal
    goal_config = load_goal_config()
    if "goal" not in goal_config:
        goal_config["goal"] = ""

    # Initialize LLM service once - use GeminiService directly
    llm = GeminiService(api_key=os.getenv("GEMINI_API_KEY"))

    # Sidebar for Sync and Goal setting
    with st.sidebar:
        st.header("Settings")
        # Time range selection with date-based descriptions
        time_ranges = [
            "Last 7 Days",
            "Last 30 Days",
            "Last 3 Months",
            "Last 6 Months",
            "Last 1 Year",
            "All Time"  # Added new option
        ]
        
        selected_range = st.selectbox(
            "Select date range to sync",
            time_ranges,
            index=1  # Default to "Last 30 Days"
        )
        if st.button("Sync Data"):
            with st.spinner("Syncing data..."):
                sync_success, sync_message = sync_data(selected_range)
                if sync_success:
                    st.success(sync_message)
                else:
                    st.error(sync_message)
        
        goal_input = st.text_area("Enter your running goal:", value=goal_config["goal"])
        
        # Goal Configuration
        st.subheader("Goal Configuration")
        total_distance_goal = st.number_input("Total Distance Goal (km)", value=goal_config.get("total_distance", 0))
        
        st.write("Specific Distance Goals")
        specific_distances = {}
        for i in range(3):
            distance = st.number_input(f"Distance {i+1} (km)", value=0.0, key=f"distance_{i}")
            if distance > 0:
                count = st.number_input(f"Number of {distance}km Runs", value=0, key=f"count_{i}")
                specific_distances[str(distance)] = count
        
        target_distance = st.number_input("Target Distance for Performance Goal (km)", value=goal_config.get("target_distance", 0.0))
        target_time = st.number_input("Target Time for Performance Goal (min)", value=goal_config.get("target_time", 0))
        
        if st.button("Save Goals"):
            goal_config["goal"] = goal_input
            goal_config["total_distance"] = total_distance_goal
            goal_config["specific_distances"] = specific_distances
            goal_config["target_distance"] = target_distance
            goal_config["target_time"] = target_time
            save_goal_config(goal_config)
            st.success("Goals saved!")

        # Add experimental features checkbox (for future use)
        if st.checkbox("Enable Experimental Features"):
            st.info("Experimental features coming soon!")

        # Add LLM selection
        st.subheader("AI Model Settings")
        llm_service = st.selectbox(
            "Select AI Model",
            ["Gemini", "Ollama (Local)"]
        )
        
        if llm_service == "Ollama (Local)":
            model_name = st.selectbox(
                "Select Ollama Model",
                ["deepseek-r1", "llama3.2"]  # Add your available models here
            )
            llm = create_llm_service(service_type="ollama", model_name=model_name)
        else:
            llm = create_llm_service(service_type="gemini", api_key=os.getenv("GEMINI_API_KEY"))

    # Fetch data from the database
    query = "SELECT * FROM strava_activities_weather"
    df = fetch_data_from_db(query)  # Get DataFrame directly

    if df.empty:
        st.info("No data available. Please sync your Strava data.")
        return
    
    df['start_date_ist'] = pd.to_numeric(df['start_date_ist'], errors='coerce')
    df.dropna(subset=['start_date_ist'], inplace=True)
    df['start_date_ist'] = pd.to_datetime(df['start_date_ist'], unit='s')
    
    # Create new tab structure
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Dashboard", 
        "Training Journey", 
        "Run Analysis",
        "Goal Center",
        "Health & Optimization",
        "AI Insights"  # New AI Insights tab
    ])

    with tab1:  # Dashboard
        st.header("Dashboard")
        
        # Top row: Key Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            last_activity = fetch_last_activity(df)
            if last_activity:
                recovery_status = calculate_recovery_status(last_activity)
                st.metric(
                    "Recovery Status", 
                    recovery_status['status'],
                    help=recovery_status['explanation']
                )
                st.caption(f"Recommended: {recovery_status['recommended_intensity']}")
        
        with col2:
            training_status = get_training_status(df)
            st.metric(
                "Training Status",
                training_status['status'],
                help=training_status['details']
            )
            consistency = calculate_training_consistency(df)
            st.caption(f"Consistency Score: {consistency}%")
        
        with col3:
            fatigue = calculate_fatigue_score(df)
            st.metric(
                "Fatigue Score",
                f"{fatigue}/100",
                help="Based on recent training load and intensity"
            )
            
        # Second row: Progress and Achievements
        st.subheader("Progress & Achievements")
        col1, col2 = st.columns(2)
        
        with col1:
            next_milestone = calculate_next_milestone(df, goal_config)
            st.metric(
                "Next Milestone",
                next_milestone['target'],
                next_milestone['progress']
            )
            
            recent_achievement = get_recent_achievement(df)
            if recent_achievement:
                st.success(recent_achievement)
        
        with col2:
            # Training load trend
            recent_load = calculate_training_load(df, days=7)
            baseline_load = calculate_training_load(df, days=30) / 4
            load_delta = ((recent_load - baseline_load) / baseline_load) * 100 if baseline_load > 0 else 0
            
            st.metric(
                "Weekly Training Load",
                f"{int(recent_load)}",
                f"{load_delta:+.1f}% vs 4-week average",
                help="Based on distance and intensity"
            )
        
        # Third row: Recommendations
        st.subheader("Recommendations")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("📋 Action Items")
            actions = generate_quick_actions(df, goal_config)
            for action in actions:
                st.info(action)
        
        with col2:
            st.write("🌤️ Weather Advisory")
            weather = get_weather_recommendation()
            st.info(
                f"{weather['recommendation']}\n\n"
                f"Details: {weather['details']}\n"
                f"Best time to run: {weather['best_time']}"
            )
        
        # Bottom section: Recent Activity Summary
        st.subheader("Recent Activity")
        if last_activity:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Distance", f"{last_activity['distance']:.1f} km")
            with col2:
                pace = last_activity['distance'] / (last_activity['moving_time'] / 3600)
                st.metric("Pace", f"{pace:.1f} km/h")
            with col3:
                st.metric("Heart Rate", f"{last_activity.get('average_heartrate', 'N/A')} bpm")
            with col4:
                st.metric("Elevation", f"{last_activity.get('total_elevation_gain', 0):.0f} m")

    with tab2:  # Training Journey
        st.header("Training Journey")
        
        # Top row: Training Calendar View
        st.subheader("Training Calendar")
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Month selector
        months = pd.date_range(start=f"{current_year}-01-01", end=f"{current_year}-12-31", freq='M')
        selected_month = st.selectbox(
            "Select Month",
            months,
            format_func=lambda x: x.strftime('%B %Y'),
            index=current_month - 1
        )
        
        # Create calendar heatmap
        calendar_data = create_training_calendar(df, selected_month)
        if calendar_data is not None:
            st.plotly_chart(calendar_data, use_container_width=True)
        
        # Second row: Progress Metrics
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Monthly Progress")
            monthly_stats = calculate_monthly_stats(df, selected_month)
            
            # Display monthly metrics
            metrics_col1, metrics_col2 = st.columns(2)
            with metrics_col1:
                st.metric("Total Distance", f"{monthly_stats['total_distance']:.1f} km")
                st.metric("Avg Distance/Run", f"{monthly_stats['avg_distance']:.1f} km")
            with metrics_col2:
                st.metric("Number of Runs", monthly_stats['num_runs'])
                st.metric("Avg Pace", f"{monthly_stats['avg_pace']:.1f} km/h")
        
        with col2:
            st.subheader("Personal Bests")
            pbs = calculate_personal_bests(df)
            for distance, pb in pbs.items():
                st.metric(
                    f"Best {distance}",
                    f"{pb['pace']:.1f} km/h",
                    f"Set on {pb['date'].strftime('%Y-%m-%d')}"
                )
        
        # Third row: Training Distribution
        st.subheader("Training Distribution")
        col1, col2 = st.columns(2)
        
        with col1:
            # Distance distribution chart
            distance_dist = create_distance_distribution(df, selected_month)
            st.plotly_chart(distance_dist, use_container_width=True)
        
        with col2:
            # Time of day distribution
            time_dist = create_time_distribution(df, selected_month)
            st.plotly_chart(time_dist, use_container_width=True)
        
        # Bottom row: Long-term Trends
        st.subheader("Long-term Trends")
        trend_metric = st.selectbox(
            "Select Metric",
            ["Weekly Distance", "Average Pace", "Training Load"]
        )
        
        trend_chart = create_long_term_trend(df, trend_metric)
        st.plotly_chart(trend_chart, use_container_width=True)

    with tab3:  # Run Analysis
        st.header("Run Analysis")
        
        # Activity selector
        recent_activities = df.sort_values('start_date_ist', ascending=False).head(10)
        selected_activity = st.selectbox(
            "Select Activity to Analyze",
            recent_activities['start_date_ist'].dt.strftime('%Y-%m-%d %H:%M - ') + 
            recent_activities['distance'].round(1).astype(str) + 'km',
            key='activity_selector'
        )
        
        # Get selected activity data
        activity_idx = recent_activities.index[
            recent_activities['start_date_ist'].dt.strftime('%Y-%m-%d %H:%M - ') + 
            recent_activities['distance'].round(1).astype(str) + 'km' == selected_activity
        ][0]
        activity_data = recent_activities.loc[activity_idx]
        
        # Top row: Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Distance", f"{activity_data['distance']:.1f} km")
        with col2:
            pace = activity_data['distance'] / (activity_data['moving_time'] / 3600)
            st.metric("Average Pace", f"{pace:.1f} km/h")
        with col3:
            st.metric("Elevation", f"{activity_data['total_elevation_gain']:.0f} m")
        with col4:
            st.metric("Heart Rate", f"{activity_data['average_heartrate']:.0f} bpm")
        
        # Second row: Split Analysis
        st.subheader("Split Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            splits_data = fetch_splits_from_db(activity_data.name)  # Using index as activity_id
            if splits_data:
                split_chart = create_detailed_split_chart(splits_data)
                st.plotly_chart(split_chart, use_container_width=True)
            else:
                st.info("No split data available for this activity")
        
        with col2:
            if splits_data:
                hr_chart = create_split_heartrate_chart_with_zones(splits_data)
                st.plotly_chart(hr_chart, use_container_width=True)
        
        # Third row: Pace Analysis
        st.subheader("Pace Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            # Pace vs Elevation
            pace_elev_chart = create_pace_elevation_chart(activity_data, splits_data)
            if pace_elev_chart is not None:
                st.plotly_chart(pace_elev_chart, use_container_width=True)
            else:
                st.error("Failed to generate the Pace Elevation Chart. Please check your data.")
        
        with col2:
            # Pace Distribution
            pace_dist = create_pace_distribution(activity_data, splits_data)
            if pace_dist is not None:  # Check if the figure is valid
                st.plotly_chart(pace_dist, use_container_width=True)
            else:
                st.error("Failed to generate the Pace Distribution Chart. Please check your data.")
        
        # Fourth row: Similar Runs Comparison
        st.subheader("Similar Runs Comparison")
        similar_runs = find_similar_runs(df, activity_data)
        if not similar_runs.empty:
            comparison_chart = create_runs_comparison_chart(similar_runs, activity_data)
            st.plotly_chart(comparison_chart, use_container_width=True)
        
        # Bottom row: Environmental Impact
        st.subheader("Environmental Factors")
        col1, col2 = st.columns(2)
        
        with col1:
            # Weather metrics
            weather_metrics = {
                "Temperature": f"{activity_data['temperature']:.1f}°C",
                "Humidity": f"{activity_data['humidity']}%",
                "Air Quality": f"AQI: {activity_data['pollution_aqi']}",
                "Conditions": activity_data['weather_conditions']
            }
            
            for metric, value in weather_metrics.items():
                st.metric(metric, value)
        
        with col2:
            # Performance correlation
            weather_impact = analyze_weather_impact(df, activity_data)
            st.write("Weather Impact Analysis")
            st.write(weather_impact['analysis'])
            if weather_impact['recommendation']:
                st.info(weather_impact['recommendation'])

    with tab4:  # Goal Center
        st.header("Goal Center")
        
        # Top row: Goal Overview
        st.subheader("2025 Goals Overview")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Volume Goals
            volume_progress = calculate_volume_goal_progress(df, goal_config)
            if volume_progress:
                total_distance = volume_progress.get('total_distance', {})
                if total_distance:
                    progress = total_distance.get('progress', 0)
                    goal = total_distance.get('goal', 0)
                    if goal > 0:
                        percentage = (progress / goal) * 100
                        st.metric(
                            "Total Distance",
                            f"{progress:.1f}/{goal:.0f} km",
                            f"{percentage:.1f}% Complete"
                        )
                        st.progress(percentage / 100)
        
        with col2:
            # Performance Goals
            performance_progress = calculate_performance_goal_progress(df, goal_config)
            if performance_progress:
                target_time = performance_progress.get('target_time')
                best_pace = performance_progress.get('best_pace')
                if target_time and best_pace:
                    target_pace = 60 / target_time  # Convert target time to km/h
                    pace_progress = (best_pace / target_pace) * 100
                    st.metric(
                        "Performance Goal",
                        f"{best_pace:.1f}/{target_pace:.1f} km/h",
                        f"{pace_progress:.1f}% of Target"
                    )
                    st.progress(min(pace_progress / 100, 1.0))
        
        with col3:
            # Consistency Goals
            consistency = calculate_training_consistency(df)
            st.metric(
                "Training Consistency",
                f"{consistency}%",
                "Based on last 30 days"
            )
            st.progress(consistency / 100)
        
        # Second row: Specific Distance Goals
        st.subheader("Distance-Specific Goals")
        specific_goals = goal_config.get("specific_distances", {})
        if specific_goals:
            for distance, target_count in specific_goals.items():
                if target_count > 0:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.write(f"{distance}km Runs")
                    with col2:
                        completed = len(df[
                            (df['distance'] >= float(distance) * 0.95) & 
                            (df['distance'] <= float(distance) * 1.05) &
                            (df['start_date_ist'].dt.year == 2025)
                        ])
                        percentage = (completed / target_count) * 100
                        st.progress(percentage / 100)
                        st.caption(f"{completed}/{target_count} ({percentage:.1f}%)")
        
        # Third row: Goal Predictions
        st.subheader("Goal Predictions")
        col1, col2 = st.columns(2)
        
        with col1:
            # Project end-of-year totals
            projections = calculate_goal_projections(df, goal_config)
            if projections:  # Check if projections is not empty
                projected_time = projections.get('projected')  # Use .get() to avoid KeyError
                target_distance = projections.get('target_distance')
                target_time = projections.get('target_time')
                # Use the values as needed
            else:
                st.error("Failed to calculate goal projections.")
        
        with col2:
            # Time to goal achievement
            goal_timing = calculate_goal_timing(df, goal_config)
            st.write("Estimated Goal Achievement")
            for goal, timing in goal_timing.items():
                st.metric(
                    goal,
                    timing['date'],
                    timing['status']
                )
        
        # Bottom row: Training Recommendations
        st.subheader("Training Recommendations")
        recommendations = generate_goal_based_recommendations(df, goal_config)
        
        for category, rec_list in recommendations.items():
            with st.expander(category):
                for rec in rec_list:
                    st.write(f"• {rec}")

    with tab5:  # Health & Optimization
        st.header("Health & Optimization")
        
        # Top row: Training Zones
        st.subheader("Training Zones")
        col1, col2 = st.columns(2)
        
        with col1:
            # Heart Rate Zones
            hr_zones = calculate_heart_rate_zones(df)
            st.write("Heart Rate Zones")
            
            # Create heart rate zones chart
            hr_zones_chart = create_heart_rate_zones_chart(hr_zones)
            st.plotly_chart(hr_zones_chart, use_container_width=True)
            
            # Display zone recommendations
            with st.expander("Zone Recommendations"):
                for zone, details in hr_zones['recommendations'].items():
                    st.write(f"**{zone}**")
                    st.write(f"• Range: {details['range']} bpm")
                    st.write(f"• Purpose: {details['purpose']}")
        
        with col2:
            # Pace Zones
            pace_zones = calculate_pace_zones(df)
            st.write("Pace Zones")
            
            # Create pace zones chart
            pace_zones_chart = create_pace_zones_chart(pace_zones)
            st.plotly_chart(pace_zones_chart, use_container_width=True)
            
            # Display zone recommendations
            with st.expander("Training Pace Guidelines"):
                for zone, details in pace_zones['recommendations'].items():
                    st.write(f"**{zone}**")
                    st.write(f"• Range: {details['range']} km/h")
                    st.write(f"• Use for: {details['purpose']}")
        
        # Second row: Health Metrics
        st.subheader("Health Metrics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Training Load
            load_metrics = calculate_training_metrics(df)
            st.metric(
                "Acute Load (7 days)",
                f"{load_metrics['acute_load']:.0f}",
                f"{load_metrics['load_change']:+.1f}%"
            )
            st.metric(
                "Chronic Load (30 days)",
                f"{load_metrics['chronic_load']:.0f}",
                help="Average weekly load over past 30 days"
            )
            
        with col2:
            # Fatigue & Recovery
            fatigue_metrics = calculate_fatigue_metrics(df)
            st.metric(
                "Fatigue Level",
                f"{fatigue_metrics['current_fatigue']}/100",
                help="Based on recent training intensity"
            )
            st.metric(
                "Recovery Score",
                f"{fatigue_metrics['recovery_score']}/100",
                help="Based on rest and training balance"
            )
            
        with col3:
            # Training Balance
            balance_metrics = calculate_training_balance(df)
            st.metric(
                "Intensity Balance",
                f"{balance_metrics['intensity_ratio']:.1f}",
                help="Ratio of high to low intensity training"
            )
            st.metric(
                "Stress Score",
                f"{balance_metrics['stress_score']}/100",
                help="Overall training stress score"
            )
        
        # Third row: Optimization Insights
        st.subheader("Optimization Insights")
        col1, col2 = st.columns(2)
        
        with col1:
            # Performance Factors
            st.write("Performance Analysis")
            performance_factors = analyze_performance_factors(df)
            
            for factor, impact in performance_factors.items():
                impact_color = "green" if impact['trend'] == "positive" else "red"
                st.markdown(
                    f"**{factor}**: {impact['analysis']} "
                    f"<span style='color:{impact_color}'>{impact['trend']}</span>",
                    unsafe_allow_html=True
                )
        
        with col2:
            # Improvement Recommendations
            st.write("Recommended Focus Areas")
            improvements = generate_improvement_recommendations(df)
            
            for area, recommendations in improvements.items():
                with st.expander(area):
                    for rec in recommendations:
                        st.write(f"• {rec}")
        
        # Bottom row: Long-term Health Trends
        st.subheader("Long-term Health Trends")
        trend_metric = st.selectbox(
            "Select Health Metric",
            ["Training Load", "Recovery Rate", "Intensity Distribution"]
        )
        
        health_trend = create_health_trend_chart(df, trend_metric)
        st.plotly_chart(health_trend, use_container_width=True)

    with tab6:  # New AI Insights tab
        st.subheader("AI Insights")
        
        # Get the last activity and formatted average metrics
        last_activity = fetch_last_activity(df)  # Pass the DataFrame as an argument
        formatted_avg_table = format_combined_average_metrics_table([calculate_average_metrics(df, "Last Activity")], ["Last Activity"])
        
        # Get volume and performance progress
        volume_progress = calculate_volume_goal_progress(df, goal_config)
        performance_progress = calculate_performance_goal_progress(df, goal_config)

        # Generate insights using the LLM service
        insights = llm.generate_insight(last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config)
        
        # Display the insights
        if insights:
            st.write(insights)
        else:
            st.error("Failed to generate insights.")

def fetch_similar_runs(df, target_distance):
    """Fetches the last 30 runs with a distance within 20% of the target distance."""
    if df.empty:
      return pd.DataFrame()

    lower_bound = target_distance * 0.8
    upper_bound = target_distance * 1.25
    
    filtered_df = df[(df['distance'] >= lower_bound) & (df['distance'] <= upper_bound)].copy()
    filtered_df.sort_values(by='start_date_local', ascending=False, inplace=True)
    return filtered_df.head(30)


if __name__ == "__main__":
    main()