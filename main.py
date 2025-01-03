import streamlit as st
import pandas as pd
from data import sync_data, fetch_data_from_db, calculate_average_metrics, fetch_last_7_runs, load_goal, save_goal, fetch_last_activity
from viz import format_last_7_runs_table, format_combined_average_metrics_table
import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

def main():
    st.set_page_config(layout="wide")
    st.title("AI Running Coach")

    # Initialize or load the user's goal
    goal = load_goal()

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
        
        goal_input = st.text_area("Enter your running goal:", value=goal)
        if st.button("Save Goal"):
            save_goal(goal_input)
            st.success("Goal saved!")
    
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
    
    # Generate AI insight
    last_activity = fetch_last_activity(df)
    if last_activity:
        st.header("AI Insight")
        
        # Calculate pace in km/h
        last_activity_pace = last_activity['distance'] / (last_activity['elapsed_time'] / 3600) if last_activity['elapsed_time'] and last_activity['distance'] else None
        
        prompt = f"""

            Rules.
            1. Distance - higher is better
            2. Average speed - higher is better
            3. Heart race - lower is better
            4. Temperature, Weather, AQI correspond to the city and not the runner.
            
            Role: You are a one of the world's best sports physicians who have helped trained elite athletes. This app is built around your persona and knowledge of giving data driven, scientific & actionable advice to help everyday runners improve.

            Goal: {goal}
            
            Analyze the user's last run compared to their recent averages:
            
            Last Run:
            - Distance: {last_activity.get('distance', 'N/A')} km
            - Pace: {last_activity_pace if last_activity_pace else 'N/A'} km/h
            - Avg Heart Rate: {last_activity.get('average_heartrate', 'N/A')} bpm
            - Elevation: {last_activity.get('total_elevation_gain', 'N/A')} meters
            - Temperature: {last_activity.get('temperature', 'N/A')} °C
            - AQI: {last_activity.get('pollution_aqi', 'N/A')}
           
            Averages (Last 30 Days):
            - Distance: {formatted_avg_table.loc['Last 30 Days', 'Avg Distance (km)']} km
            - Pace: {formatted_avg_table.loc['Last 30 Days', 'Avg Pace (km/h)']} km/h
            - Avg Heart Rate: {formatted_avg_table.loc['Last 30 Days', 'Avg HR (bpm)']} bpm
            - Elevation: {formatted_avg_table.loc['Last 30 Days', 'Avg Elevation (m)']} meters
             - Temperature: {formatted_avg_table.loc['Last 30 Days', 'Avg Temp (°C)']} °C
            - AQI: {formatted_avg_table.loc['Last 30 Days', 'Avg AQI']}
           
            
            1. Provide a concise analysis of of the last run compared to the recent averages. Also, analyse the impact of external factors like weather, temperature to see their impact.
            2. Provide a actionable recommendation that will help user in progressing towards their goal based on this run and your analysis above.
            3. Deeply look at the data and see what other interesting patterns you can see that are not obvious 
        """
        
        try:
            response = model.generate_content(prompt)
            st.markdown(response.text)
        except Exception as e:
            st.error(f"Error generating AI insight: {e}")

if __name__ == "__main__":
    main()