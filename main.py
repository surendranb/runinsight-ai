import streamlit as st
import pandas as pd
from data import sync_data, fetch_data_from_db, calculate_average_metrics, fetch_last_7_runs, load_goal_config, save_goal_config, fetch_last_activity, calculate_volume_goal_progress, calculate_performance_goal_progress
from viz import format_last_7_runs_table, format_combined_average_metrics_table, create_trend_chart, format_performance_goal_progress, format_runs_with_splits_table, create_split_pace_chart, create_split_heartrate_chart
import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

def main():
    st.set_page_config(layout="wide")
    st.title("AI Running Coach")

    # Initialize or load the user's goal
    goal_config = load_goal_config()
    if "goal" not in goal_config:
        goal_config["goal"] = ""

    # Sidebar for Sync and Goal setting
    with st.sidebar:
        st.header("Settings")
         # Time range selection with date-based descriptions
        time_ranges = [
            "Last 7 Days",
            "Last 30 Days",
             "Last 3 Months"
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
    
    # Fetch data from the database
    query = "SELECT * FROM strava_activities_weather"
    data, columns = fetch_data_from_db(query)
    
    if not data:
        st.info("No data available. Please sync your Strava data.")
        return
    
    df = pd.DataFrame(data, columns=columns)
    df['start_date_ist'] = pd.to_numeric(df['start_date_ist'], errors='coerce')
    df.dropna(subset=['start_date_ist'], inplace=True)
    df['start_date_ist'] = pd.to_datetime(df['start_date_ist'], unit='s')
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Trend Analysis", "AI Insights", "Goals", "Performance Tracking"])

    with tab1:
        # Fetch and display Last 7 runs table
        st.header("Last 7 Runs")
        last_7_runs = fetch_last_7_runs(df)
        formatted_runs_table = format_last_7_runs_table(last_7_runs)
        st.dataframe(formatted_runs_table, use_container_width=True)

        # Calculate and display average metrics table
        st.header("Average Metrics")
        periods = ["Last 7 Days", "Last 30 Days", "Last 3 Months", "Last 6 Months", "Last 1 Year", "All Time"]
        avg_metrics_list = []
        for period in periods:
            avg_metrics = calculate_average_metrics(df, period)
            avg_metrics_list.append(avg_metrics)
        
        formatted_avg_table = format_combined_average_metrics_table(avg_metrics_list, periods)
        st.dataframe(formatted_avg_table, use_container_width=True)

    with tab2:
        # Trend Analysis
        st.header("Trend Analysis")
        trend_metrics = ["pace", "distance"]
        for metric in trend_metrics:
            fig = create_trend_chart(df, metric, f"{metric.capitalize()} Trend")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"No data available to plot {metric} trend")

    with tab3:
        # Generate AI insight
        last_activity = fetch_last_activity(df)
        if last_activity:
            st.header("AI Insight")
            
            # Calculate pace in km/h
            last_activity_pace = last_activity['distance'] / (last_activity['elapsed_time'] / 3600) if last_activity['elapsed_time'] and last_activity['distance'] else None
            
            # Calculate progress towards volume goals
            volume_progress = calculate_volume_goal_progress(df, goal_config)
            
            # Calculate progress towards performance goals
            performance_progress = calculate_performance_goal_progress(df, goal_config)
            
            prompt = f"""
                Goal: {goal_config["goal"]}
                
                Analyze the user's last run compared to their recent averages:
                
                Last Run:
                - Distance: {last_activity.get('distance', 'N/A')} km
                - Pace: {last_activity_pace if last_activity_pace else 'N/A'} km/h
                - Avg Heart Rate: {last_activity.get('average_heartrate', 'N/A')} bpm
                - Elevation: {last_activity.get('total_elevation_gain', 'N/A')} meters
                - Temperature: {last_activity.get('temperature', 'N/A')} °C
                - AQI: {last_activity.get('pollution_aqi', 'N/A')}
               
                Averages:
                - Last 7 Days:
                    - Distance: {formatted_avg_table.loc['Last 7 Days', 'Avg Distance (km)']} km
                    - Pace: {formatted_avg_table.loc['Last 7 Days', 'Avg Pace (km/h)']} km/h
                    - Avg Heart Rate: {formatted_avg_table.loc['Last 7 Days', 'Avg HR (bpm)']} bpm
                    - Elevation: {formatted_avg_table.loc['Last 7 Days', 'Avg Elevation (m)']} meters
                    - Temperature: {formatted_avg_table.loc['Last 7 Days', 'Avg Temp (°C)']} °C
                    - AQI: {formatted_avg_table.loc['Last 7 Days', 'Avg AQI']}
                - Last 30 Days:
                    - Distance: {formatted_avg_table.loc['Last 30 Days', 'Avg Distance (km)']} km
                    - Pace: {formatted_avg_table.loc['Last 30 Days', 'Avg Pace (km/h)']} km/h
                    - Avg Heart Rate: {formatted_avg_table.loc['Last 30 Days', 'Avg HR (bpm)']} bpm
                    - Elevation: {formatted_avg_table.loc['Last 30 Days', 'Avg Elevation (m)']} meters
                    - Temperature: {formatted_avg_table.loc['Last 30 Days', 'Avg Temp (°C)']} °C
                    - AQI: {formatted_avg_table.loc['Last 30 Days', 'Avg AQI']}
                - Last 3 Months:
                    - Distance: {formatted_avg_table.loc['Last 3 Months', 'Avg Distance (km)']} km
                    - Pace: {formatted_avg_table.loc['Last 3 Months', 'Avg Pace (km/h)']} km/h
                    - Avg Heart Rate: {formatted_avg_table.loc['Last 3 Months', 'Avg HR (bpm)']} bpm
                    - Elevation: {formatted_avg_table.loc['Last 3 Months', 'Avg Elevation (m)']} meters
                    - Temperature: {formatted_avg_table.loc['Last 3 Months', 'Avg Temp (°C)']} °C
                    - AQI: {formatted_avg_table.loc['Last 3 Months', 'Avg AQI']}
                - Last 6 Months:
                    - Distance: {formatted_avg_table.loc['Last 6 Months', 'Avg Distance (km)']} km
                    - Pace: {formatted_avg_table.loc['Last 6 Months', 'Avg Pace (km/h)']} km/h
                    - Avg Heart Rate: {formatted_avg_table.loc['Last 6 Months', 'Avg HR (bpm)']} bpm
                    - Elevation: {formatted_avg_table.loc['Last 6 Months', 'Avg Elevation (m)']} meters
                    - Temperature: {formatted_avg_table.loc['Last 6 Months', 'Avg Temp (°C)']} °C
                    - AQI: {formatted_avg_table.loc['Last 6 Months', 'Avg AQI']}
                - Last 1 Year:
                    - Distance: {formatted_avg_table.loc['Last 1 Year', 'Avg Distance (km)']} km
                    - Pace: {formatted_avg_table.loc['Last 1 Year', 'Avg Pace (km/h)']} km/h
                    - Avg Heart Rate: {formatted_avg_table.loc['Last 1 Year', 'Avg HR (bpm)']} bpm
                    - Elevation: {formatted_avg_table.loc['Last 1 Year', 'Avg Elevation (m)']} meters
                    - Temperature: {formatted_avg_table.loc['Last 1 Year', 'Avg Temp (°C)']} °C
                    - AQI: {formatted_avg_table.loc['Last 1 Year', 'Avg AQI']}
                - All Time:
                    - Distance: {formatted_avg_table.loc['All Time', 'Avg Distance (km)']} km
                    - Pace: {formatted_avg_table.loc['All Time', 'Avg Pace (km/h)']} km/h
                    - Avg Heart Rate: {formatted_avg_table.loc['All Time', 'Avg HR (bpm)']} bpm
                    - Elevation: {formatted_avg_table.loc['All Time', 'Avg Elevation (m)']} meters
                    - Temperature: {formatted_avg_table.loc['All Time', 'Avg Temp (°C)']} °C
                    - AQI: {formatted_avg_table.loc['All Time', 'Avg AQI']}
                
                Volume Goal Progress (2025):
                - Total Distance: {volume_progress.get('total_distance', {}).get('progress', 'N/A')} / {volume_progress.get('total_distance', {}).get('goal', 'N/A')} km
                { "".join([f"- Number of {k.split('_')[1].replace('km','')}km Runs: {v.get('progress', 'N/A')} / {v.get('goal', 'N/A')} \n" for k,v in volume_progress.items() if k.startswith('runs_')])}
                
                Performance Goal Progress:
                - Best Pace: {performance_progress.get('best_pace', 'N/A') if performance_progress.get('best_pace') is not None else 'N/A'} km/h
                - Rolling Average Pace (last 10 runs): {performance_progress.get('rolling_average_pace', 'N/A') if performance_progress.get('rolling_average_pace') is not None else 'N/A'} km/h
                - Target Time: {performance_progress.get('target_time', 'N/A')} min
                
                Based on this data, provide specific and actionable recommendations to help the user achieve their goal.
            """
            
            try:
                response = model.generate_content(prompt)
                if response.parts:
                    st.markdown(response.parts[0].text)
                else:
                    st.error("No text content found in the AI response.")
            except Exception as e:
                st.error(f"Error generating AI insight: {e}")
    
    with tab4:
        st.header("Goals")
        
        st.subheader("Volume Goal Progress (2025)")
        volume_progress = calculate_volume_goal_progress(df, goal_config)
        if volume_progress:
            total_distance_progress = volume_progress.get("total_distance", {})
            if total_distance_progress:
                goal = total_distance_progress.get("goal", 0)
                progress = total_distance_progress.get("progress", 0)
                if goal > 0:
                    progress_percentage = (progress / goal) * 100
                else:
                    progress_percentage = 0
                st.progress(progress_percentage/100, text=f"Total Distance: {progress:.2f}/{goal} km")
            
            
            specific_distances = goal_config.get("specific_distances", {})
            for i, (distance, goal_count) in enumerate(specific_distances.items()):
                key = f"runs_{distance}km"
                progress_data = volume_progress.get(key, {})
                progress_count = progress_data.get("progress", 0)
                if goal_count > 0:
                    progress_percentage = (progress_count / goal_count) * 100
                else:
                    progress_percentage = 0
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{distance}km Runs**")
                with col2:
                    st.progress(progress_percentage/100, text=f"{progress_count} / {goal_count}")
        else:
            st.info("No volume goals set or no data available for 2025.")
        
        st.subheader("Performance Goal Progress")
        performance_progress = calculate_performance_goal_progress(df, goal_config)
        if performance_progress:
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Target Time (min)", performance_progress.get("target_time", "N/A"))
            with col2:
                best_pace = performance_progress.get('best_pace', 'N/A')
                st.metric("Best Pace (km/h)", f"{best_pace:.2f}" if isinstance(best_pace, (int, float)) else best_pace)
            with col3:
                rolling_average_pace = performance_progress.get("rolling_average_pace", None)
                target_time = performance_progress.get("target_time", None)
                if rolling_average_pace is not None and target_time is not None:
                    target_pace_kmh = 60 / target_time if target_time > 0 else None
                    if target_pace_kmh is not None:
                        if rolling_average_pace >= target_pace_kmh:
                            st.markdown(f"<p style='color:green;'>Rolling Avg Pace (km/h): {rolling_average_pace:.2f} ✅</p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p style='color:red;'>Rolling Avg Pace (km/h): {rolling_average_pace:.2f} ❌</p>", unsafe_allow_html=True)
                    else:
                        st.metric("Rolling Avg Pace (km/h)", f"{rolling_average_pace:.2f}" if isinstance(rolling_average_pace, (int, float)) else rolling_average_pace)
                else:
                    st.metric("Rolling Avg Pace (km/h)", "N/A")
            
            # formatted_performance_progress = format_performance_goal_progress(performance_progress)
            # st.dataframe(formatted_performance_progress, use_container_width=True)
        else:
            st.info("No performance goal set or no data available.")

    with tab5:
        st.header("Performance Tracking")
        if goal_config.get("target_distance"):
                target_distance = float(goal_config.get("target_distance"))
                similar_runs = fetch_similar_runs(df, target_distance)
                if not similar_runs.empty:
                    formatted_runs = format_runs_with_splits_table(similar_runs)
                    st.dataframe(pd.DataFrame(formatted_runs), use_container_width=True) # convert to dataframe
                    fig = create_split_pace_chart(formatted_runs)
                    if fig:
                       st.plotly_chart(fig, use_container_width=True)
                    else:
                       st.info("No split data available to generate the chart")
                    fig_hr = create_split_heartrate_chart(formatted_runs)
                    if fig_hr:
                       st.plotly_chart(fig_hr, use_container_width=True)
                    else:
                        st.info("No heart rate data available to generate the chart")
                else:
                    st.info("No similar runs found for the target distance.")
        else:
            st.info("Please set a target distance in settings.")

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