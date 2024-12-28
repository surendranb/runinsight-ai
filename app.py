import streamlit as st
from strava_data import get_last_activity, generate_gemini_prompt, get_gemini_response, fetch_and_store_activities, create_or_update_database, get_user_goals, authenticate_strava, DEFAULT_USER_ID
import sqlite3

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

# Display User Goals
user_goals = get_user_goals()
if user_goals:
    st.header("Your Current Goal")
    st.write(user_goals)

last_activity = get_last_activity()

if last_activity:
    st.header("Recent Run Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Distance (km)", f"{last_activity.get('distance', 'N/A'):.2f}")
    col2.metric("Elapsed Time (s)", f"{last_activity.get('elapsed_time', 'N/A'):.0f}")
    col3.metric("Average Pace (min/km)", f"{last_activity.get('elapsed_time', 0) / last_activity.get('distance', 1) / 60:.2f}" if last_activity.get('distance') else "N/A")
    col1.metric("Average Heart Rate", f"{last_activity.get('average_heartrate', 'N/A'):.0f}")
    col2.metric("Suffer Score", f"{last_activity.get('suffer_score', 'N/A')}")
    col3.metric("Calories", f"{last_activity.get('calories', 'N/A'):.0f}")
    
    st.header("AI Coaching Feedback")
    prompt = generate_gemini_prompt(last_activity)
    response = get_gemini_response(prompt)
    st.write(response)
    
    st.header("All Activities")
    st.dataframe([last_activity])
else:
    st.write("No activities found in the database.")