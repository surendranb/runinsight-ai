import streamlit as st
from strava_data import get_last_activity, generate_gemini_prompt, get_gemini_response, fetch_and_store_activities, create_or_update_database, get_user_goals, authenticate_strava, DEFAULT_USER_ID, get_activity_paces, get_progress_summary, generate_gemini_prompt_with_details
import sqlite3
from datetime import datetime, timedelta

st.title("AI Running Coach")

# Sidebar Controls
with st.sidebar:
    st.header("Settings")
    
    # Goal Setting UI
    st.subheader("Set/Edit Your Running Goal")
    user_goals = get_user_goals()
    goal_narrative = st.text_input("Your Current Goal", value=user_goals if user_goals else "")
    with st.form("goal_form"):
        submitted = st.form_submit_button("Update Goal")
        if submitted:
            create_or_update_database()
            # Store the goal narrative
            if goal_narrative:
                conn = sqlite3.connect("running_coach.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO goals (user_id, goal_narrative)
                    VALUES (?, ?)
                """, (DEFAULT_USER_ID, goal_narrative))
                conn.commit()
                conn.close()
                st.success("Goal updated successfully!")
    
    # Sync Data Button
    num_years = st.number_input("Number of Years to Sync", min_value=1, value=1, step=1)
    if st.button("Sync Data"):
        client = authenticate_strava()
        if client:
            fetch_and_store_activities(client, num_years)
        else:
            st.error("Authentication failed. Please try again.")
    
    # Display Runs per Year
    st.subheader("Runs per Year")
    conn = sqlite3.connect("running_coach.db")
    cursor = conn.cursor()
    cursor.execute("SELECT strftime('%Y', start_date) as year, COUNT(*) FROM activities GROUP BY year")
    runs_per_year = cursor.fetchall()
    conn.close()
    if runs_per_year:
        for year, count in runs_per_year:
            st.write(f"{year}: {count} runs")
    else:
        st.write("No runs found in the database.")
    
    # # Display Progress Summary
    # st.subheader("Progress Summary")
    # progress_summary = get_progress_summary()
    # st.write(f"Longest Run: {progress_summary.get('longest_run', 'N/A'):.2f} km" if isinstance(progress_summary.get('longest_run'), (int, float)) else f"Longest Run: N/A")
    # st.write(f"Fastest Pace: {progress_summary.get('fastest_pace', 'N/A'):.2f} min/km" if isinstance(progress_summary.get('fastest_pace'), (int, float)) else f"Fastest Pace: N/A")
    # st.write(f"Total Distance: {progress_summary.get('total_distance', 'N/A'):.2f} km" if isinstance(progress_summary.get('total_distance'), (int, float)) else f"Total Distance: N/A")
    # st.write(f"Average Runs per Week: {progress_summary.get('average_runs_per_week', 'N/A'):.2f}" if isinstance(progress_summary.get('average_runs_per_week'), (int, float)) else f"Average Runs per Week: N/A")

    # Display Progress Summary
    st.subheader("Progress Summary")
    progress_summary = get_progress_summary()

    for metric_name, metric_key in [("Longest Run", "longest_run"), ("Fastest Pace", "fastest_pace"), ("Total Distance", "total_distance"), ("Average Runs per Week", "average_runs_per_week")]:
        value = progress_summary.get('Overall', {}).get(metric_key)  # Use .get() to handle missing data
        display_value = f"{value:.2f}" if isinstance(value, (int, float)) else "N/A" # Format only if numerical
        st.write(f"{metric_name}: {display_value} {'km' if metric_key in ('longest_run', 'total_distance') else ''}{'min/km' if metric_key == 'fastest_pace' else ''}")





# Display User Goals
user_goals = get_user_goals()
if user_goals:
    st.header("Your Current Goal")
    st.write(user_goals)

last_activity = get_last_activity()

if last_activity:
    tab1, tab2, tab3, tab4 = st.tabs(["Recent Runs & Coaching", "Pace Metrics", "Heart Rate Metrics", "Distance Metrics"])
    
    with tab1:
        st.header("Recent Runs")
        conn = sqlite3.connect("running_coach.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activities ORDER BY id DESC LIMIT 7")
        recent_runs = cursor.fetchall()
        conn.close()
        if recent_runs:
            columns = [col[0] for col in cursor.description]
            recent_runs_dicts = [dict(zip(columns, row)) for row in recent_runs]
            st.dataframe(recent_runs_dicts)
        else:
            st.write("No activities found in the database.")

        # AI Coaching Feedback (Use data from last 30 days)
        st.header("AI Coaching Feedback")

        thirty_days_ago = datetime.now() - timedelta(days=30)
        conn = sqlite3.connect("running_coach.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activities WHERE start_date >= ?", (thirty_days_ago.isoformat(),))
        recent_runs_for_feedback = cursor.fetchall() # Data for AI feedback
        conn.close()

        if recent_runs_for_feedback:
            # Construct detailed prompt with aggregated data
            prompt = generate_gemini_prompt_with_details(recent_runs_for_feedback, get_user_goals())
            response = get_gemini_response(prompt)
            st.write(response)
        else:
            st.write("No recent runs found for AI coaching feedback.")
    
    with tab2:
        st.header("Pace Metrics")
        progress_summary = get_progress_summary()
        time_periods = ["Last 7 days", "Last 30 days", "Last 90 days", "This year", "Last year", "Overall"]
        
        pace_metrics_data = {}
        for time_period in time_periods:
            pace_metrics_data[time_period] = {
                "Average Pace": f"{progress_summary.get(time_period, {}).get('average_pace', 'N/A'):.2f} min/km" if isinstance(progress_summary.get(time_period, {}).get('fastest_pace'), (int, float)) else "N/A",
                "Pace Variability": f"{progress_summary.get(time_period, {}).get('pace_variability', 'N/A'):.2f} min/km" if isinstance(progress_summary.get(time_period, {}).get('pace_variability'), (int, float)) else "N/A",
                "Best Pace (5k)": f"{progress_summary.get(time_period, {}).get('best_5k', 'N/A'):.2f} min/km" if isinstance(progress_summary.get(time_period, {}).get('best_5k'), (int, float)) else "N/A", # Added best 5k
                "Best Pace (10k)": f"{progress_summary.get(time_period, {}).get('best_10k', 'N/A'):.2f} min/km" if isinstance(progress_summary.get(time_period, {}).get('best_10k'), (int, float)) else "N/A"  # Added best 10k
            }
        st.table(pace_metrics_data)

        st.header("AI Insights on Pace")
        prompt = generate_gemini_prompt_with_details(recent_runs_for_feedback, get_user_goals()) # Use 30 day data
        pace_insights = get_gemini_response(f"{prompt}\n\nFocus your analysis on pace information, providing insights on pace consistency and areas for improvement.")  # Add specific instructions
        st.write(pace_insights)
    
    with tab3:
        st.header("Heart Rate Metrics")
        progress_summary = get_progress_summary()
        time_periods = ["Last 7 days", "Last 30 days", "Last 90 days", "This year", "Last year", "Overall"]
        
        heart_rate_metrics_data = {}
        for time_period in time_periods:
            heart_rate_metrics_data[time_period] = {
                "Average Heart Rate": f"{progress_summary.get(time_period, {}).get('average_heart_rate', 'N/A'):.2f} bpm" if isinstance(progress_summary.get(time_period, {}).get('average_heart_rate'), (int, float)) else "N/A"
            }
        st.table(heart_rate_metrics_data)

        st.header("AI Insights on Heart Rate")
        prompt = generate_gemini_prompt_with_details(recent_runs_for_feedback, get_user_goals()) # Use 30 day data
        heart_rate_insights = get_gemini_response(f"{prompt}\n\nFocus your analysis on heart rate data and its relation to training load and recovery.  Provide insights and recommendations.") # Specific instructions for Heart Rate
        st.write(heart_rate_insights)
    
    with tab4:
        st.header("Distance Metrics")
        progress_summary = get_progress_summary()
        time_periods = ["Last 7 days", "Last 30 days", "Last 90 days", "This year", "Last year", "Overall"]
        
        distance_metrics_data = {}
        for time_period in time_periods:
            distance_metrics_data[time_period] = {
                "Total Distance": f"{progress_summary.get(time_period, {}).get('total_distance', 'N/A'):.2f} km" if isinstance(progress_summary.get(time_period, {}).get('total_distance'), (int, float)) else "N/A",
                "Longest Run Distance": f"{progress_summary.get(time_period, {}).get('longest_run', 'N/A'):.2f} km" if isinstance(progress_summary.get(time_period, {}).get('longest_run'), (int, float)) else "N/A"
            }
        st.table(distance_metrics_data)

        st.header("AI Insights on Distance and Training Volume")
        prompt = generate_gemini_prompt_with_details(recent_runs_for_feedback, get_user_goals())  # Use 30 day data
        distance_insights = get_gemini_response(f"{prompt}\n\nFocus your analysis on distance, training volume, and the user's goals related to these aspects. Suggest actionable steps for achieving their goals.") # Specific instructions for Distance
        st.write(distance_insights)