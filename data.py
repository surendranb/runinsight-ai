import os
import stravalib
import requests
import time
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import sqlite3
import pandas as pd
import streamlit as st


load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
REDIRECT_URI = "http://localhost:8000/authorized"

DATABASE_NAME = "ai_running_coach.db"
GOAL_FILE = "user_goal.json"

# Rate limiting variables
STRAVA_REQUEST_DELAY = 10  # 10 seconds delay between requests

def create_database_and_tables():
    """Creates the SQLite database and tables with correct type definitions."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create combined strava_activities_weather table (WITH CORRECT TYPES)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strava_activities_weather (
            id INTEGER PRIMARY KEY,
            start_date TEXT,
            start_date_local TEXT,
            distance REAL,
            elapsed_time REAL,
            moving_time REAL,
            max_heartrate INTEGER,
            average_heartrate REAL,
            suffer_score REAL,
            calories REAL,
            map_summary_polyline TEXT,
            total_elevation_gain REAL,
            average_speed REAL,
            max_speed REAL,
            average_cadence REAL,
            type TEXT,
            start_latitude REAL,
            start_longitude REAL,
            timezone TEXT,
            gear_id TEXT,
            device_name TEXT,
            temperature REAL,
            feels_like REAL,
            humidity REAL,
            weather_conditions TEXT,
            pollution_aqi INTEGER,
            pollution_pm25 REAL,
            pollution_co REAL,
            pollution_no REAL,
            pollution_no2 REAL,
            pollution_o3 REAL,
            pollution_so2 REAL,
            pollution_pm10 REAL,
            pollution_nh3 REAL,
            city_name TEXT,
            start_date_ist INTEGER
        )
    """)

    # Create splits_data table (WITH CORRECT TYPES)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS splits_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER,
            split INTEGER,
            distance REAL,
            elapsed_time REAL,
            average_speed REAL,
            elevation_difference REAL,
            moving_time REAL,
            average_heartrate REAL,
            average_grade_adjusted_speed REAL,
            FOREIGN KEY (activity_id) REFERENCES strava_activities_weather(id)
        )
    """)

    # Create best_efforts_data table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS best_efforts_data (
            activity_id INTEGER,
            name TEXT,
            distance REAL,
            elapsed_time REAL,
            start_date TEXT,
            PRIMARY KEY (activity_id, name)
        )
    """)

    conn.commit()
    conn.close()

def authenticate_strava(code=None):
    """Authenticates with the Strava API using OAuth 2.0."""
    client = stravalib.Client()
    
    try:
        # If we have a code, exchange it for tokens
        if code:
            token_response = client.exchange_code_for_token(
                client_id=int(STRAVA_CLIENT_ID),
                client_secret=STRAVA_CLIENT_SECRET,
                code=code
            )
            client.access_token = token_response['access_token']
            return client
            
        # If no code, redirect to Strava authorization
        authorize_url = client.authorization_url(
            client_id=int(STRAVA_CLIENT_ID),
            redirect_uri=REDIRECT_URI,
            scope=['read_all', 'activity:read_all']
        )
        
        # Use Streamlit to handle the OAuth flow
        st.write("Please authorize access to your Strava account")
        st.markdown(f"[Click here to authorize]({authorize_url})")
        
        # Add input for the authorization code
        auth_code = st.text_input("Enter the authorization code from the URL:")
        if auth_code:
            token_response = client.exchange_code_for_token(
                client_id=int(STRAVA_CLIENT_ID),
                client_secret=STRAVA_CLIENT_SECRET,
                code=auth_code
            )
            client.access_token = token_response['access_token']
            return client
            
        return None
        
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return None

def stream_activities(client, after=None):
    """
    Streams activities one at a time from Strava API.
    Stops when an activity older than the cutoff date is encountered.
    """
    try:
        print("[Strava] Starting activity stream...")
        activity_count = 0
        for activity in client.get_activities():
            activity_count += 1
            activity_date = activity.start_date.replace(tzinfo=timezone.utc)
            if after and activity_date < after:
                print(f"[Strava] Reached cutoff date after {activity_count} activities")
                break
            print(f"[Strava] Processing activity {activity_count}: {activity.id}")
            yield activity
            time.sleep(STRAVA_REQUEST_DELAY)  # 10 second delay between Strava API calls

    except Exception as e:
        print(f"[Strava] Error streaming activities: {e}")

def process_activity(client, activity_id):
    """Process a single Strava activity."""
    try:
        print(f"[Strava] Fetching details for activity {activity_id}")
        activity = client.get_activity(activity_id)
        if activity:
            print(f"[Strava] Successfully fetched activity {activity_id}")
        return activity
    except Exception as e:
        print(f"[Strava] Error fetching activity {activity_id}: {e}")
        return None

def fetch_openweathermap_data(latitude, longitude, timestamp, elapsed_time):
    """Fetches historical weather data and city name from OpenWeatherMap API."""
    print("[Weather] Fetching weather data...")
    base_url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
    air_pollution_url = "http://api.openweathermap.org/data/2.5/air_pollution/history"
    reverse_geocode_url = "http://api.openweathermap.org/geo/1.0/reverse"

    params = {
        "lat": latitude,
        "lon": longitude,
        "dt": int(timestamp),
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric",
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        weather_data = response.json()

        # Calculate end time for pollution data (activity end time)
        end_timestamp = int(timestamp) + int(elapsed_time)

        air_pollution_params = {
            "lat": latitude,
            "lon": longitude,
            "start": int(timestamp),
            "end": end_timestamp,
            "appid": OPENWEATHERMAP_API_KEY
        }
        air_pollution_response = requests.get(air_pollution_url, params=air_pollution_params)
        air_pollution_response.raise_for_status()
        air_pollution_data = air_pollution_response.json()

        # Fetch city name
        reverse_geocode_params = {
            "lat": latitude,
            "lon": longitude,
            "appid": OPENWEATHERMAP_API_KEY,
            "limit": 1
        }
        reverse_geocode_response = requests.get(reverse_geocode_url, params=reverse_geocode_params)
        reverse_geocode_response.raise_for_status()
        city_data = reverse_geocode_response.json()
        city_name = city_data[0]["name"] if city_data else None
        return weather_data, air_pollution_data, city_name
    except requests.exceptions.RequestException as e:
        return None, None, None

def insert_strava_data(conn, activity, weather_data, air_pollution_data, city_name, ist_timestamp):
    """Inserts Strava activity and weather data into the database."""
    cursor = conn.cursor()
    
    try:
        if activity.start_date:
            start_date = activity.start_date.strftime('%Y-%m-%d %H:%M:%S')
            start_date_local = activity.start_date_local.strftime('%Y-%m-%d %H:%M:%S') if activity.start_date_local else None
        else:
            start_date = None
            start_date_local = None
    except AttributeError:
        start_date = None
        start_date_local = None

    # Handle map data safely: Explicitly convert None to empty string
    try:
        if (hasattr(activity, 'map') and 
            activity.map is not None and 
            hasattr(activity.map, 'summary_polyline')):
            map_polyline = activity.map.summary_polyline
            if map_polyline is None:
                map_polyline = ""
            else:
                try:
                    # Ensure proper encoding of the polyline
                    map_polyline = str(map_polyline).encode('utf-8').decode('utf-8')
                except:
                    print(f"[DB] Failed to encode map polyline for activity {activity.id}")
                    map_polyline = ""
        else:
            map_polyline = ""
    except Exception as e:
        print(f"[DB] Error processing map data for activity {activity.id}: {e}")
        map_polyline = ""

    # Get location data safely
    if activity.start_latlng:
        start_latitude = activity.start_latlng.lat
        start_longitude = activity.start_latlng.lon
    else:
        start_latitude = None
        start_longitude = None

    # Convert Strava units to numeric values
    try:
        average_speed = float(activity.average_speed.magnitude) if hasattr(activity.average_speed, 'magnitude') else activity.average_speed
        total_elevation_gain = float(activity.total_elevation_gain.magnitude) if hasattr(activity.total_elevation_gain, 'magnitude') else activity.total_elevation_gain
        max_speed = float(activity.max_speed.magnitude) if hasattr(activity.max_speed, 'magnitude') else activity.max_speed
    except AttributeError as e:
        print(f"[DB] Error converting units for activity {activity.id}: {e}")
        average_speed = None
        total_elevation_gain = None
        max_speed = None

    if weather_data and air_pollution_data:
        closest_pollution_data = None
        if "list" in air_pollution_data and air_pollution_data["list"]:
            timestamp = time.mktime(activity.start_date.timetuple())
            closest_time_diff = float('inf')
            for item in air_pollution_data["list"]:
                time_diff = abs(item["dt"] - int(timestamp))
                if time_diff < closest_time_diff:
                    closest_time_diff = time_diff
                    closest_pollution_data = item

        strava_weather_data = (
            activity.id,
            start_date,
            start_date_local,
            float(activity.distance) / 1000 if activity.distance else None,
            float(activity.elapsed_time.total_seconds()) if isinstance(activity.elapsed_time, timedelta) else float(activity.elapsed_time),
            float(activity.moving_time.total_seconds()) if isinstance(activity.moving_time, timedelta) else float(activity.moving_time),
            activity.max_heartrate,
            activity.average_heartrate,
            activity.suffer_score,
            activity.calories,
            map_polyline,
            total_elevation_gain,
            average_speed,
            max_speed,
            activity.average_cadence,
            str(activity.type),
            start_latitude,
            start_longitude,
            str(activity.timezone),
            activity.gear_id,
            activity.device_name,
            weather_data["data"][0]["temp"] if weather_data and "data" in weather_data and weather_data["data"] else None,
            weather_data["data"][0]["feels_like"] if weather_data and "data" in weather_data and weather_data["data"] else None,
            weather_data["data"][0]["humidity"] if weather_data and "data" in weather_data and weather_data["data"] else None,
            weather_data["data"][0]["weather"][0]["description"] if weather_data and "data" in weather_data and weather_data["data"] and "weather" in weather_data["data"][0] else None,
            closest_pollution_data["main"]["aqi"] if closest_pollution_data else None,
            closest_pollution_data["components"]["pm2_5"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["co"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["no"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["no2"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["o3"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["so2"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["pm10"] if closest_pollution_data and "components" in closest_pollution_data else None,
            closest_pollution_data["components"]["nh3"] if closest_pollution_data and "components" in closest_pollution_data else None,
            city_name,
            ist_timestamp
        )
    else:  # Consistent handling of map_polyline
        strava_weather_data = (
            activity.id,
            start_date,
            start_date_local,
            float(activity.distance) / 1000 if activity.distance else None,
            float(activity.elapsed_time.total_seconds()) if isinstance(activity.elapsed_time, timedelta) else float(activity.elapsed_time),
            float(activity.moving_time.total_seconds()) if isinstance(activity.moving_time, timedelta) else float(activity.moving_time),
            activity.max_heartrate,
            activity.average_heartrate,
            activity.suffer_score,
            activity.calories,
            map_polyline,
            total_elevation_gain,
            average_speed,
            max_speed,
            activity.average_cadence,
            str(activity.type),
            start_latitude,
            start_longitude,
            str(activity.timezone),
            activity.gear_id,
            activity.device_name,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            city_name,
            ist_timestamp
        )

    # Add this right before the cursor.execute() call
    print(f"[DB] Map polyline type: {type(map_polyline)}")
    print(f"[DB] Map polyline length: {len(map_polyline)}")

    try:
        # Verify all parameters are of supported SQLite types
        for i, param in enumerate(strava_weather_data):
            if param is not None and not isinstance(param, (int, float, str, bytes)):
                print(f"[DB] Warning: Parameter {i} has unsupported type: {type(param)}")
                # Convert to string if not a basic type
                strava_weather_data = list(strava_weather_data)
                strava_weather_data[i] = str(param)
                strava_weather_data = tuple(strava_weather_data)

        cursor.execute("""
                INSERT INTO strava_activities_weather (
                id, start_date, start_date_local, distance, elapsed_time,
                moving_time, max_heartrate, average_heartrate, suffer_score,
                calories, map_summary_polyline, total_elevation_gain,
                average_speed, max_speed, average_cadence, type,
                start_latitude, start_longitude, timezone, gear_id,
                device_name, temperature, feels_like, humidity,
                weather_conditions, pollution_aqi, pollution_pm25,
                pollution_co, pollution_no, pollution_no2, pollution_o3,
                pollution_so2, pollution_pm10, pollution_nh3, city_name,
                start_date_ist
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, strava_weather_data)
        conn.commit()
        
        # Process splits
        if activity.splits_metric:
            for split in activity.splits_metric:
                try:
                    split_data = (
                        int(activity.id),
                        int(split.split) if split.split else 0,  # Ensure split number is an integer
                        float(split.distance) if split.distance else 0.0,
                        float(split.elapsed_time.total_seconds()) if isinstance(split.elapsed_time, timedelta) else float(split.elapsed_time) if split.elapsed_time else 0.0,
                        float(split.average_speed) if split.average_speed else 0.0,
                        float(split.elevation_difference) if split.elevation_difference else 0.0,
                        float(split.moving_time.total_seconds()) if isinstance(split.moving_time, timedelta) else float(split.moving_time) if split.moving_time else 0.0,
                        float(split.average_heartrate) if split.average_heartrate else None,
                        float(split.average_grade_adjusted_speed) if split.average_grade_adjusted_speed else 0.0
                    )
                    cursor.execute("""
                        INSERT INTO splits_data (
                            activity_id, split, distance, elapsed_time, 
                            average_speed, elevation_difference, moving_time, 
                            average_heartrate, average_grade_adjusted_speed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, split_data)
                    conn.commit()
                except Exception as e:
                    print(f"[DB] Error inserting split {split.split} for activity {activity.id}: {e}")
                    continue

        # Process best efforts
        if hasattr(activity, 'best_efforts') and activity.best_efforts:
            for effort in activity.best_efforts:
                try:
                    effort_data = (
                        int(activity.id),
                        str(effort.name) if effort.name else "",
                        float(effort.distance) if effort.distance else 0.0,
                        float(effort.elapsed_time.total_seconds()) if isinstance(effort.elapsed_time, timedelta) else float(effort.elapsed_time) if effort.elapsed_time else 0.0,
                        str(effort.start_date.strftime('%Y-%m-%d %H:%M:%S')) if effort.start_date else None
                    )
                    cursor.execute("""
                        INSERT INTO best_efforts_data (
                            activity_id, name, distance, elapsed_time, start_date
                        ) VALUES (?, ?, ?, ?, ?)
                    """, effort_data)
                    conn.commit()
                except Exception as e:
                    print(f"[DB] Error inserting best effort '{effort.name if hasattr(effort, 'name') else 'unknown'}' for activity {activity.id}: {e}")
                    continue

        print(f"[DB] Successfully processed activity {activity.id}")
        return True
    except Exception as e:
        print(f"[DB] Error saving activity {activity.id}: {e}")
        conn.rollback()
        return False

def fetch_data_from_db(query):
    """Fetch data from SQLite database."""
    try:
        conn = sqlite3.connect('ai_running_coach.db')
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Convert speed values from m/s to km/h
        if 'average_speed' in df.columns:
            df['average_speed'] = pd.to_numeric(df['average_speed'], errors='coerce')
            df['average_speed'] = df['average_speed'] * 3.6

        # Convert elevation values from meters to numeric
        if 'total_elevation_gain' in df.columns:
            df['total_elevation_gain'] = pd.to_numeric(df['total_elevation_gain'], errors='coerce')

        # Ensure other numeric columns are properly converted
        numeric_columns = ['distance', 'elapsed_time', 'moving_time', 'average_heartrate', 
                         'temperature', 'pollution_aqi']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df
    except Exception as e:
        return pd.DataFrame()

def activity_exists(conn, activity_id):
    """Check if an activity already exists in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM strava_activities_weather WHERE id = ?", (activity_id,))
    return cursor.fetchone() is not None

def sync_data(time_range="Last 30 Days"):
    """
    Syncs running activities from Strava API and stores them with weather data.
    
    Args:
        time_range (str): Time range to sync ("Last 7 Days", "Last 30 Days", "Last 3 Months", 
                         "Last 6 Months", "Last 1 Year", "All Time")
    
    Returns:
        tuple: (success_bool, message_str)
    """
    try:
        # Create database and tables if they don't exist
        create_database_and_tables()

        # Initialize Strava client
        client = authenticate_strava()
        if not client:
            return False, "Failed to authenticate with Strava"

        # Set the cutoff date based on the provided time range
        time_ranges = {
            "Last 7 Days": 7,
            "Last 30 Days": 30,
            "Last 3 Months": 90,
            "Last 6 Months": 180,
            "Last 1 Year": 365,
            "All Time": None  # No cutoff date for all time
        }
        
        days = time_ranges.get(time_range)
        after_datetime = None
        if days is not None:
            after_datetime = (datetime.now() - timedelta(days=days)).replace(tzinfo=timezone.utc)
        
        # Stream and process activities
        activities_processed = 0
        conn = sqlite3.connect(DATABASE_NAME)
        max_retries = 3

        try:
            # Modified to handle 'All Time' case
            activities_stream = client.get_activities() if after_datetime is None else client.get_activities(after=after_datetime)
            
            for activity in activities_stream:
                # Skip non-running activities
                if activity.type != 'Run':
                    continue

                # Check if activity already exists
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM strava_activities_weather WHERE id = ?", (activity.id,))
                if cursor.fetchone():
                    continue

                # Fetch detailed activity data with retry mechanism
                detailed_activity = None
                for attempt in range(max_retries):
                    try:
                        detailed_activity = client.get_activity(activity.id)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            print(f"Failed to fetch activity {activity.id} after {max_retries} attempts: {e}")
                            continue
                        time.sleep(STRAVA_REQUEST_DELAY)

                if not detailed_activity:
                    continue

                # Fetch weather data if location is available
                weather_data = None
                air_pollution_data = None
                city_name = None
                
                if detailed_activity.start_latlng:
                    activity_timestamp = int(detailed_activity.start_date.timestamp())
                    elapsed_time_seconds = int(detailed_activity.elapsed_time.total_seconds()) if isinstance(detailed_activity.elapsed_time, timedelta) else int(detailed_activity.elapsed_time)

                    weather_data, air_pollution_data, city_name = fetch_openweathermap_data(
                        detailed_activity.start_latlng.lat,
                        detailed_activity.start_latlng.lon,
                        activity_timestamp,
                        elapsed_time_seconds
                    )

                # Store timestamp at start of day in IST
                ist_timestamp = int(datetime.combine(detailed_activity.start_date.date(),
                                               datetime.min.time()).timestamp())

                # Insert data into database
                try:
                    insert_strava_data(conn, detailed_activity, weather_data, air_pollution_data,
                                     city_name, ist_timestamp)
                    activities_processed += 1
                except Exception as e:
                    print(f"Error processing activity {activity.id}: {e}")
                    continue

                time.sleep(STRAVA_REQUEST_DELAY)  # Respect API rate limits

        finally:
            conn.close()

        return True, f"Successfully synced {activities_processed} new activities."

    except Exception as e:
        return False, f"Error during sync: {str(e)}"

def calculate_average_metrics(df, period, target_distance=None):
    """Calculates average metrics for a given period."""
    now = datetime.now()
    if period == "Last 7 Days":
        cutoff = now - timedelta(days=7)
    elif period == "Last 30 Days":
        cutoff = now - timedelta(days=30)
    elif period == "Last 3 Months":
        cutoff = now - timedelta(days=90)
    elif period == "Last 6 Months":
        cutoff = now - timedelta(days=180)
    elif period == "Last 1 Year":
        cutoff = now - timedelta(days=365)
    elif period == "All Time":
      cutoff = datetime.min
    else:
        cutoff = datetime.min

    filtered_df = df[df['start_date_ist'] >= cutoff].copy()

    if filtered_df.empty:
        return {}

    avg_metrics = filtered_df[[
        'distance',
        'elapsed_time',
        'average_speed',
        'average_heartrate',
        'total_elevation_gain',
        'temperature',
        'pollution_aqi'
    ]].mean().to_dict()

    # Additional info
    avg_metrics['num_runs'] = len(filtered_df)

    if target_distance:
        # Calculate best pace for the target distance
        target_distance_runs = filtered_df[filtered_df['distance'] == target_distance]
        if not target_distance_runs.empty:
            best_pace_run = target_distance_runs.sort_values(by='average_speed', ascending=False).iloc[0]
            avg_metrics['best_pace'] = best_pace_run['average_speed']
        else:
            avg_metrics['best_pace'] = None
    return avg_metrics

def fetch_last_7_runs(df):
    """Fetches the last 7 runs from the provided DataFrame."""
    if df.empty:
        return []

    df_sorted = df.sort_values(by='start_date_ist', ascending=False).head(7)
    return df_sorted.to_dict(orient='records')

def load_goal_config():
    """Loads the user's goal configuration from the JSON file."""
    try:
        with open(GOAL_FILE, "r") as f:
            data = json.load(f)
            return data.get("goal_config", {})
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_goal_config(goal_config):
    """Saves the user's goal configuration to the JSON file."""
    with open(GOAL_FILE, "w") as f:
        json.dump({"goal_config": goal_config}, f)

def fetch_last_activity(df):
    """Fetches the last activity from the provided DataFrame."""
    if df.empty:
        return None
    df_sorted = df.sort_values(by='start_date_ist', ascending=False)
    return df_sorted.iloc[0].to_dict()

def calculate_volume_goal_progress(df, goal_config):
    """Calculates progress towards volume goals for 2025."""
    if df.empty or not goal_config:
        return {}

    try:
        df_2025 = df[pd.to_datetime(df['start_date_local'], format='mixed').dt.year == 2025].copy()
    except Exception:
        return {}

    if df_2025.empty:
        return {}

    progress = {}

    # Calculate total distance
    total_distance_goal = goal_config.get("total_distance", 0)
    total_distance_progress = df_2025['distance'].sum()
    progress["total_distance"] = {
        "goal": total_distance_goal,
        "progress": total_distance_progress
    }

    # Calculate number of runs for specific distances
    specific_distances = goal_config.get("specific_distances", {})
    for distance, goal_count in specific_distances.items():
        distance = float(distance)
        if distance == 5:
            filtered_runs = df_2025[(df_2025['distance'] >= 5) & (df_2025['distance'] < 10)]
            run_count = len(filtered_runs)
        elif distance == 10:
            filtered_runs = df_2025[(df_2025['distance'] >= 10) & (df_2025['distance'] < 21)]
            run_count = len(filtered_runs)
        elif distance == 21:
            filtered_runs = df_2025[df_2025['distance'] >= 21]
            run_count = len(filtered_runs)
        else:
            run_count = 0
        progress[f"runs_{distance}km"] = {
            "goal": goal_count,
            "progress": run_count
        }

    return progress

def calculate_performance_goal_progress(df, goal_config):
    """Calculates progress towards performance goals."""
    if df.empty or not goal_config:
        return {}

    target_distance = goal_config.get("target_distance")
    target_time = goal_config.get("target_time")

    if not target_distance or not target_time:
        return {}

    target_distance = float(target_distance)

    # Filter for runs of the target distance
    target_distance_runs = df[df['distance'] == target_distance].copy()

    if target_distance_runs.empty:
        return {
            "best_pace": None,
            "rolling_average_pace": None,
            "target_time": target_time
        }

    # Calculate best pace
    best_pace_run = target_distance_runs.sort_values(by='average_speed', ascending=False).iloc[0]
    best_pace = best_pace_run['average_speed']

    # Calculate rolling average of the last 10 runs
    target_distance_runs = target_distance_runs.sort_values(by='start_date_ist', ascending=False).head(10)
    rolling_average_pace = target_distance_runs['average_speed'].mean()

    return {
        "best_pace": best_pace,
        "rolling_average_pace": rolling_average_pace,
        "target_time": target_time
    }

def calculate_recovery_status(last_activity):
    """Calculate current recovery status based on last activity."""
    if not last_activity:
        return {
            "status": "Fresh",
            "explanation": "No recent activities",
            "color": "green",
            "recommended_intensity": "Any"
        }
    
    # Calculate hours since last activity
    last_activity_time = pd.to_datetime(last_activity['start_date_local'])
    hours_since = (datetime.now() - last_activity_time).total_seconds() / 3600
    
    # Get intensity of last activity (using distance as a proxy)
    distance = last_activity.get('distance', 0)
    avg_hr = last_activity.get('average_heartrate', 150)
    
    # Calculate recovery status based on activity intensity and time passed
    if distance > 20 or avg_hr > 170:  # Long run or high intensity
        if hours_since < 48:
            return {
                "status": "Recovery Needed",
                "explanation": "Recent hard effort detected",
                "color": "red",
                "recommended_intensity": "Rest or Very Easy"
            }
        elif hours_since < 72:
            return {
                "status": "Recovering",
                "explanation": "Good for easy training",
                "color": "yellow",
                "recommended_intensity": "Easy"
            }
    elif distance > 10 or avg_hr > 150:  # Medium run
        if hours_since < 24:
            return {
                "status": "Recovering",
                "explanation": "Recent medium effort",
                "color": "yellow",
                "recommended_intensity": "Easy"
            }
    
    return {
        "status": "Fresh",
        "explanation": "Well rested",
        "color": "green",
        "recommended_intensity": "Any"
    }

def calculate_next_milestone(df, goal_config):
    """Calculate the next milestone based on goals."""
    if df.empty or not goal_config:
        return {"target": "No goals set", "progress": ""}
    
    # Check volume goals
    total_distance_goal = goal_config.get("total_distance", 0)
    if total_distance_goal:
        current_distance = df[df['start_date_ist'].dt.year == 2025]['distance'].sum()
        remaining = total_distance_goal - current_distance
        return {
            "target": f"{total_distance_goal}km in 2025",
            "progress": f"{current_distance:.1f}km done"
        }
    
    return {"target": "Set goals", "progress": ""}

def get_recent_achievement(df):
    """Identify recent achievements."""
    if df.empty:
        return None
        
    recent_df = df.sort_values('start_date_ist', ascending=False).head(5)
    
    # Check for personal bests
    best_5k = df[df['distance'] >= 5]['average_speed'].max()
    recent_best = recent_df[recent_df['distance'] >= 5]['average_speed'].max()
    
    if recent_best >= best_5k:
        return "New 5K Personal Best! 🎉"
    
    return None

def generate_quick_actions(df, goal_config):
    """Generate recommended actions based on recent activity."""
    actions = []
    
    if df.empty:
        return ["Start by syncing your Strava data"]
    
    last_run = df.iloc[0]
    days_since_long_run = (
        datetime.now() - 
        df[df['distance'] > 10]['start_date_ist'].max()
    ).days
    
    if days_since_long_run > 7:
        actions.append("Time for a long run this week")
    
    # Add more action generation logic
    return actions

def generate_weather_alert(df):
    """Generate weather alerts for running."""
    # Implementation depends on your weather data source
    return None

def calculate_training_load(df, days=30):
    """Calculate training load based on recent activities."""
    if df.empty:
        return 0
    
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=days))]
    
    # Basic training load calculation using distance and heart rate
    training_load = recent_df.apply(
        lambda row: (row['distance'] * row['average_heartrate']) 
        if pd.notnull(row['average_heartrate']) 
        else row['distance'] * 150,  # Default HR if missing
        axis=1
    ).sum()
    
    return training_load

def calculate_training_consistency(df, days=30):
    """Calculate training consistency score (0-100)."""
    if df.empty:
        return 0
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Create date range for all days
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Count runs per day
    runs_per_day = df[df['start_date_ist'] >= start_date].groupby(
        pd.to_datetime(df['start_date_ist']).dt.date
    ).size()
    
    # Calculate consistency score
    total_days = len(date_range)
    days_with_runs = len(runs_per_day)
    consistency_score = (days_with_runs / total_days) * 100
    
    return round(consistency_score, 1)

def get_training_status(df):
    """
    Calculate overall training status based on recent activities.
    Returns a status and color indicator.
    """
    if df.empty:
        return {"status": "Unknown", "color": "gray", "details": "No training data available"}
    
    recent_load = calculate_training_load(df, days=7)
    baseline_load = calculate_training_load(df, days=30) / 4  # Average weekly load
    consistency = calculate_training_consistency(df)
    
    # Determine status based on load comparison and consistency
    if recent_load < baseline_load * 0.5:
        return {
            "status": "Detraining",
            "color": "red",
            "details": "Training load has dropped significantly"
        }
    elif recent_load > baseline_load * 1.5:
        return {
            "status": "Overreaching",
            "color": "orange",
            "details": "Training load is high, consider recovery"
        }
    elif consistency < 30:
        return {
            "status": "Inconsistent",
            "color": "yellow",
            "details": "Training consistency needs improvement"
        }
    else:
        return {
            "status": "Maintaining",
            "color": "green",
            "details": "Good training balance"
        }

def get_weather_recommendation():
    """Get weather-based running recommendations."""
    # This would typically connect to a weather API
    # For now, returning a placeholder
    return {
        "recommendation": "Good conditions for running",
        "details": "Moderate temperature and low humidity",
        "best_time": "Evening"
    }

def calculate_fatigue_score(df, days=7):
    """Calculate fatigue score based on recent training load."""
    if df.empty:
        return 0
    
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=days))]
    
    # Calculate fatigue based on distance and intensity
    fatigue_score = recent_df.apply(
        lambda row: (row['distance'] * (row['average_heartrate'] / 150)) 
        if pd.notnull(row['average_heartrate']) 
        else row['distance'],
        axis=1
    ).sum()
    
    return min(100, round(fatigue_score / days, 1))

def calculate_monthly_stats(df, selected_month):
    """Calculate statistics for the selected month."""
    if df.empty:
        return {
            "total_distance": 0,
            "avg_distance": 0,
            "num_runs": 0,
            "avg_pace": 0
        }
    
    # Filter data for selected month
    mask = (df['start_date_ist'].dt.year == selected_month.year) & \
           (df['start_date_ist'].dt.month == selected_month.month)
    month_data = df[mask].copy()
    
    if month_data.empty:
        return {
            "total_distance": 0,
            "avg_distance": 0,
            "num_runs": 0,
            "avg_pace": 0
        }
    
    return {
        "total_distance": month_data['distance'].sum(),
        "avg_distance": month_data['distance'].mean(),
        "num_runs": len(month_data),
        "avg_pace": month_data['average_speed'].mean()
    }

def calculate_personal_bests(df):
    """Calculate personal bests for different distances."""
    if df.empty:
        return {}
    
    distances = [5, 10, 21.1]  # 5K, 10K, Half Marathon
    pbs = {}
    
    for dist in distances:
        # Filter runs close to the target distance (within 2%)
        mask = (df['distance'] >= dist * 0.98) & (df['distance'] <= dist * 1.02)
        filtered_runs = df[mask]
        
        if not filtered_runs.empty:
            best_run = filtered_runs.loc[filtered_runs['average_speed'].idxmax()]
            pbs[f"{dist}km"] = {
                "pace": best_run['average_speed'],
                "date": best_run['start_date_ist']
            }
    
    return pbs

def find_similar_runs(df, current_run):
    """Finds runs with similar distance and conditions."""
    if df.empty:
        return pd.DataFrame()
    
    distance_margin = 0.1  # 10% margin
    temp_margin = 5  # 5 degrees margin
    
    similar = df[
        (df['distance'].between(
            current_run['distance'] * (1-distance_margin),
            current_run['distance'] * (1+distance_margin)
        )) &
        (df['temperature'].between(
            current_run['temperature'] - temp_margin,
            current_run['temperature'] + temp_margin
        ))
    ].copy()
    
    return similar.sort_values('start_date_ist', ascending=False).head(5)

def analyze_weather_impact(df, current_run):
    """Analyzes the impact of weather conditions on performance."""
    if df.empty:
        return {
            "analysis": "Not enough data for analysis",
            "recommendation": None
        }
    
    # Compare with similar runs in different conditions
    similar_distance = df[
        df['distance'].between(
            current_run['distance'] * 0.9,
            current_run['distance'] * 1.1
        )
    ]
    
    if len(similar_distance) < 5:
        return {
            "analysis": "Not enough similar runs for comparison",
            "recommendation": None
        }
    
    # Calculate average pace in different temperature ranges
    temp_ranges = pd.cut(similar_distance['temperature'], bins=3)
    pace_by_temp = similar_distance.groupby(temp_ranges)['average_speed'].mean()
    
    # Find optimal temperature range
    optimal_temp_range = pace_by_temp.idxmax()
    
    return {
        "analysis": f"Your pace tends to be best in {optimal_temp_range}",
        "recommendation": "Consider scheduling future runs during cooler hours" 
        if current_run['temperature'] > optimal_temp_range.right 
        else None
    }

def calculate_goal_projections(df, goal_config):
    """Calculates projections based on current performance and goals."""
    if df.empty or not goal_config:
        return {}

    target_distance = goal_config.get("target_distance")
    target_time = goal_config.get("target_time")

    if not target_distance or not target_time:
        return {}

    # Example projection logic
    recent_runs = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=30))]
    average_speed = recent_runs['average_speed'].mean() if not recent_runs.empty else 0

    # Calculate projected time to reach the target distance
    projected_time = target_distance / average_speed if average_speed > 0 else None

    return {
        "projected": projected_time,
        "target_distance": target_distance,
        "target_time": target_time
    }

def calculate_goal_timing(df, goal_config):
    """Calculate estimated dates for goal achievement."""
    if df.empty or not goal_config:
        return {}
    
    timing = {}
    
    # Calculate total distance goal timing
    total_distance_goal = goal_config.get("total_distance", 0)
    if total_distance_goal:
        current_distance = df[df['start_date_ist'].dt.year == 2025]['distance'].sum()
        remaining_distance = total_distance_goal - current_distance
        
        # Calculate daily rate
        daily_rate = df[
            df['start_date_ist'] >= (datetime.now() - timedelta(days=30))
        ]['distance'].sum() / 30
        
        if daily_rate > 0:
            days_to_goal = remaining_distance / daily_rate
            goal_date = datetime.now() + timedelta(days=days_to_goal)
            
            timing["Distance Goal"] = {
                "date": goal_date.strftime('%Y-%m-%d'),
                "status": "On Track" if goal_date.year == 2025 else "Behind Schedule"
            }
    
    return timing

def generate_goal_based_recommendations(df, goal_config):
    """Generate training recommendations based on goals and progress."""
    if df.empty or not goal_config:
        return {}
    
    recommendations = {
        "Volume Training": [],
        "Performance Training": [],
        "Recovery & Maintenance": []
    }
    
    # Volume recommendations
    total_distance_goal = goal_config.get("total_distance", 0)
    if total_distance_goal > 0:
        completed_distance = df['distance'].sum()
        if completed_distance < total_distance_goal:
            recommendations["Volume Training"].append(
                f"Increase weekly distance to reach {total_distance_goal} km goal."
            )
    
    # Performance recommendations
    target_pace = goal_config.get("target_pace", 0)
    if target_pace > 0:
        avg_pace = df['average_speed'].mean()
        if avg_pace < target_pace:
            recommendations["Performance Training"].append(
                "Incorporate interval training to improve pace."
            )
    
    # Recovery recommendations
    avg_rest_days = calculate_average_rest_days(df)
    if avg_rest_days < 1:
        recommendations["Recovery & Maintenance"].append(
            "Include at least one rest day between runs for proper recovery."
        )
    
    return recommendations

def calculate_heart_rate_zones(df):
    """Calculate heart rate zones and their distribution."""
    if df.empty:
        return {
            "zones": {},
            "recommendations": {}
        }
    
    # Get max heart rate from data or use age-based estimation
    max_hr = df['max_heartrate'].max() or 220 - 30  # Assuming age 30 if no data
    
    # Define heart rate zones
    zones = {
        "Zone 1 (Recovery)": (0.5 * max_hr, 0.6 * max_hr),
        "Zone 2 (Base)": (0.6 * max_hr, 0.7 * max_hr),
        "Zone 3 (Tempo)": (0.7 * max_hr, 0.8 * max_hr),
        "Zone 4 (Threshold)": (0.8 * max_hr, 0.9 * max_hr),
        "Zone 5 (Maximum)": (0.9 * max_hr, max_hr)
    }
    
    # Calculate time spent in each zone
    zone_distribution = {}
    for zone_name, (lower, upper) in zones.items():
        zone_time = len(df[
            (df['average_heartrate'] >= lower) & 
            (df['average_heartrate'] < upper)
        ])
        zone_distribution[zone_name] = zone_time
    
    # Generate recommendations
    recommendations = {
        "Zone 1 (Recovery)": {
            "range": f"{int(zones['Zone 1 (Recovery)'][0])}-{int(zones['Zone 1 (Recovery)'][1])}",
            "purpose": "Active recovery and warm-up"
        },
        "Zone 2 (Base)": {
            "range": f"{int(zones['Zone 2 (Base)'][0])}-{int(zones['Zone 2 (Base)'][1])}",
            "purpose": "Aerobic endurance and fat burning"
        },
        "Zone 3 (Tempo)": {
            "range": f"{int(zones['Zone 3 (Tempo)'][0])}-{int(zones['Zone 3 (Tempo)'][1])}",
            "purpose": "Aerobic power and lactate threshold improvement"
        },
        "Zone 4 (Threshold)": {
            "range": f"{int(zones['Zone 4 (Threshold)'][0])}-{int(zones['Zone 4 (Threshold)'][1])}",
            "purpose": "Anaerobic endurance and VO2 max"
        },
        "Zone 5 (Maximum)": {
            "range": f"{int(zones['Zone 5 (Maximum)'][0])}-{int(zones['Zone 5 (Maximum)'][1])}",
            "purpose": "Maximum performance and speed"
        }
    }
    
    return {
        "zones": zone_distribution,
        "recommendations": recommendations
    }

def calculate_pace_zones(df):
    """Calculate pace zones based on recent performance."""
    if df.empty:
        return {
            "zones": {},
            "recommendations": {}
        }
    
    # Calculate recent best pace
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=90))]
    if recent_df.empty:
        recent_df = df
    
    best_pace = recent_df['average_speed'].max()
    
    # Define pace zones as percentages of best pace
    zones = {
        "Easy": (0.6 * best_pace, 0.7 * best_pace),
        "Base": (0.7 * best_pace, 0.8 * best_pace),
        "Tempo": (0.8 * best_pace, 0.9 * best_pace),
        "Threshold": (0.9 * best_pace, 0.95 * best_pace),
        "Speed": (0.95 * best_pace, best_pace)
    }
    
    # Calculate distribution
    zone_distribution = {}
    for zone_name, (lower, upper) in zones.items():
        zone_runs = len(df[
            (df['average_speed'] >= lower) & 
            (df['average_speed'] < upper)
        ])
        zone_distribution[zone_name] = zone_runs
    
    # Generate recommendations
    recommendations = {
        "Easy": {
            "range": f"{zones['Easy'][0]:.1f}-{zones['Easy'][1]:.1f}",
            "purpose": "Recovery runs and long slow distance"
        },
        "Base": {
            "range": f"{zones['Base'][0]:.1f}-{zones['Base'][1]:.1f}",
            "purpose": "Aerobic endurance building"
        },
        "Tempo": {
            "range": f"{zones['Tempo'][0]:.1f}-{zones['Tempo'][1]:.1f}",
            "purpose": "Lactate threshold development"
        },
        "Threshold": {
            "range": f"{zones['Threshold'][0]:.1f}-{zones['Threshold'][1]:.1f}",
            "purpose": "Race pace training"
        },
        "Speed": {
            "range": f"{zones['Speed'][0]:.1f}-{zones['Speed'][1]:.1f}",
            "purpose": "Speed development and intervals"
        }
    }
    
    return {
        "zones": zone_distribution,
        "recommendations": recommendations
    }

def calculate_training_metrics(df):
    """Calculate various training load metrics."""
    if df.empty:
        return {
            "acute_load": 0,
            "chronic_load": 0,
            "load_change": 0
        }
    
    # Calculate acute (7-day) load
    acute_load = calculate_training_load(df, days=7)
    
    # Calculate chronic (30-day) load
    chronic_load = calculate_training_load(df, days=30)
    
    # Calculate load change
    baseline_load = chronic_load / 4  # Weekly average from chronic load
    load_change = ((acute_load - baseline_load) / baseline_load * 100) if baseline_load > 0 else 0
    
    return {
        "acute_load": acute_load,
        "chronic_load": chronic_load,
        "load_change": load_change
    }

def calculate_fatigue_metrics(df):
    """Calculate fatigue and recovery metrics."""
    if df.empty:
        return {
            "current_fatigue": 0,
            "recovery_score": 100
        }
    
    # Calculate recent training intensity
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=7))]
    if recent_df.empty:
        return {
            "current_fatigue": 0,
            "recovery_score": 100
        }
    
    # Calculate fatigue based on recent training load and intensity
    recent_load = calculate_training_load(recent_df)
    baseline_load = calculate_training_load(df, days=30) / 4
    
    fatigue_score = min(100, (recent_load / baseline_load * 70)) if baseline_load > 0 else 0
    recovery_score = max(0, 100 - fatigue_score)
    
    return {
        "current_fatigue": int(fatigue_score),
        "recovery_score": int(recovery_score)
    }

def calculate_training_balance(df):
    """Calculate training balance metrics."""
    if df.empty:
        return {
            "intensity_ratio": 0,
            "stress_score": 0
        }
    
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=30))]
    if recent_df.empty:
        return {
            "intensity_ratio": 0,
            "stress_score": 0
        }
    
    # Calculate intensity ratio (high intensity / low intensity)
    avg_speed = recent_df['average_speed'].mean()
    high_intensity = len(recent_df[recent_df['average_speed'] > avg_speed * 1.1])
    low_intensity = len(recent_df[recent_df['average_speed'] <= avg_speed * 1.1])
    
    intensity_ratio = high_intensity / low_intensity if low_intensity > 0 else 0
    
    # Calculate stress score
    recent_load = calculate_training_load(recent_df)
    optimal_load = calculate_training_load(df, days=90) / 12  # Monthly average
    stress_score = min(100, (recent_load / optimal_load * 70)) if optimal_load > 0 else 0
    
    return {
        "intensity_ratio": intensity_ratio,
        "stress_score": int(stress_score)
    }

def analyze_performance_factors(df):
    """Analyze various factors affecting performance."""
    if df.empty:
        return {}
    
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=30))]
    if recent_df.empty:
        return {}
    
    factors = {}
    
    # Analyze consistency
    runs_per_week = len(recent_df) / 4
    factors["Training Frequency"] = {
        "analysis": f"Averaging {runs_per_week:.1f} runs per week",
        "trend": "positive" if runs_per_week >= 3 else "negative"
    }
    
    # Analyze intensity distribution
    avg_speed = recent_df['average_speed'].mean()
    intensity_ratio = len(recent_df[recent_df['average_speed'] > avg_speed * 1.1]) / len(recent_df)
    factors["Intensity Balance"] = {
        "analysis": f"{intensity_ratio:.0%} high-intensity runs",
        "trend": "positive" if 0.2 <= intensity_ratio <= 0.3 else "negative"
    }
    
    # Analyze recovery
    avg_rest_days = calculate_average_rest_days(recent_df)
    factors["Recovery Pattern"] = {
        "analysis": f"Average {avg_rest_days:.1f} days between runs",
        "trend": "positive" if 1 <= avg_rest_days <= 3 else "negative"
    }
    
    return factors

def generate_improvement_recommendations(df):
    """Generate specific recommendations for improvement."""
    if df.empty:
        return {}
    
    recommendations = {
        "Training Structure": [],
        "Recovery": [],
        "Performance": []
    }
    
    # Analyze recent training patterns
    recent_df = df[df['start_date_ist'] >= (datetime.now() - timedelta(days=30))]
    if recent_df.empty:
        return recommendations
    
    # Training structure recommendations
    runs_per_week = len(recent_df) / 4
    if runs_per_week < 3:
        recommendations["Training Structure"].append(
            "Gradually increase running frequency to 3-4 times per week"
        )
    elif runs_per_week > 6:
        recommendations["Training Structure"].append(
            "Consider including more recovery days to prevent overtraining"
        )
    
    # Recovery recommendations
    avg_rest_days = calculate_average_rest_days(recent_df)
    if avg_rest_days < 1:
        recommendations["Recovery"].append(
            "Include at least one rest day between runs for proper recovery"
        )
    
    # Performance recommendations
    avg_speed = recent_df['average_speed'].mean()
    intensity_ratio = len(recent_df[recent_df['average_speed'] > avg_speed * 1.1]) / len(recent_df)
    
    if intensity_ratio < 0.2:
        recommendations["Performance"].append(
            "Include one high-intensity session per week for performance gains"
        )
    elif intensity_ratio > 0.3:
        recommendations["Performance"].append(
            "Reduce high-intensity sessions to prevent burnout"
        )
    
    return recommendations

def calculate_average_rest_days(df):
    """Calculate average days between runs."""
    if df.empty or len(df) < 2:
        return 0
    
    dates = sorted(df['start_date_ist'].unique())
    rest_days = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
    
    return sum(rest_days) / len(rest_days) if rest_days else 0