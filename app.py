import streamlit as st
from datetime import datetime, timezone
import os
from data.fetcher import DataFetcher
from data.database import Database
from data.helpers import calculate_date_range, process_activity_data

def main():
    st.set_page_config(page_title="AI Running Coach", layout="wide")
    st.title("AI Running Coach - Data Sync")

    # Initialize database
    db = Database()
    
    # Sidebar for sync controls
    with st.sidebar:
        st.header("Data Sync")
        sync_options = [
            "Last 7 Days",
            "Last 14 Days",
            "Last 30 Days",
            "Last 90 Days",
            "This Year"
        ]
        selected_range = st.selectbox(
            "Select date range to sync",
            sync_options,
            index=2  # Default to 30 days
        )
        
        if st.button("🔄 Sync Data"):
            with st.spinner(f"Syncing activities for {selected_range}..."):
                fetcher = DataFetcher()
                after_date = calculate_date_range(selected_range)
                
                activities = fetcher.fetch_activities(after_date)
                
                activities_synced = 0
                for activity in activities:
                    activity_data, splits_data = process_activity_data(activity)
                    if not db.activity_exists(activity_data['id']):
                        if db.store_activity(activity_data, splits_data):
                            activities_synced += 1
                
                if activities_synced > 0:
                    st.success(f"Successfully synced {activities_synced} new activities")
                else:
                    st.info("No new activities to sync")

        # Show last sync info
        last_activity = db.get_latest_activity_date()
        if last_activity:
            st.write(f"Last synced activity: {last_activity.strftime('%Y-%m-%d')}")

    # Main area placeholder
    st.write("Ready to start the AI coaching journey!")

if __name__ == "__main__":
    main()