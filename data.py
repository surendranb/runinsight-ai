import os
import stravalib
import requests
import time
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import sqlite3
import pandas as pd


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
    """Creates the SQLite database and tables if they don't exist."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create combined strava_activities_weather table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strava_activities_weather (
            id,                  
            start_date,         
            start_date_local,   
            distance,           
            elapsed_time,       
            moving_time,        
            max_heartrate,      
            average_heartrate,  
            suffer_score,       
            calories,           
            map_summary_polyline, 
            total_elevation_gain, 
            average_speed,     
            max_speed,         
            average_cadence,   
            type,              
            start_latitude,    
            start_longitude,   
            timezone,          
            gear_id,          
            device_name,      
            temperature,      
            feels_like,       
            humidity,         
            weather_conditions, 
            pollution_aqi,    
            pollution_pm25,   
            pollution_co,     
            pollution_no,     
            pollution_no2,    
            pollution_o3,     
            pollution_so2,    
            pollution_pm10,   
            pollution_nh3,    
            city_name,        
            start_date_ist    
        )
    """)

    conn.commit()
    conn.close()

def authenticate_strava(code=None):
    """Authenticates with the Strava API using OAuth 2.0."""
    client = stravalib.Client()
    print("[Strava] Authenticating...")

    # Check if we have a refresh token
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
    if refresh_token:
        try:
            refresh_response = client.refresh_access_token(
                client_id=STRAVA_CLIENT_ID,
                client_secret=STRAVA_CLIENT_SECRET,
                refresh_token=refresh_token
            )
            client.access_token = refresh_response['access_token']
            os.environ["STRAVA_ACCESS_TOKEN"] = client.access_token
            print("[Strava] Authentication successful")
            return client
        except Exception as e:
            print("[Strava] Token refresh failed")
            return None

    # If no refresh token or refresh failed, start the OAuth flow
    authorize_url = client.authorization_url(
        client_id=STRAVA_CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=["read_all", "activity:read_all"]
    )
    
    print(f"\n[Strava] Please visit this URL to authorize: {authorize_url}")
    code = input("[Strava] Enter the authorization code from the URL: ")
    
    try:
        token_response = client.exchange_code_for_token(
            client_id=STRAVA_CLIENT_ID,
            client_secret=STRAVA_CLIENT_SECRET,
            code=code
        )
        client.access_token = token_response['access_token']
        os.environ["STRAVA_ACCESS_TOKEN"] = client.access_token
        os.environ["STRAVA_REFRESH_TOKEN"] = token_response['refresh_token']
        print("[Strava] New authentication successful")
        return client
    except Exception as e:
        print("[Strava] Authentication failed")
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
    print(f"[DB] Processing activity {activity.id}")

    # Insert into strava_activities_weather table
    if activity.start_latlng:
        start_latitude = activity.start_latlng.lat
        start_longitude = activity.start_latlng.lon
    else:
        start_latitude = None
        start_longitude = None
    
    if activity.start_date:
        start_date_local = activity.start_date_local.isoformat() if activity.start_date_local else None
    else:
        start_date_local = None
    
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
            activity.start_date.isoformat() if activity.start_date else None,
            start_date_local,
            float(activity.distance) / 1000 if activity.distance else None,
            float(activity.elapsed_time) if activity.elapsed_time else None,
            float(activity.moving_time) if activity.moving_time else None,
            activity.max_heartrate,
            activity.average_heartrate,
            activity.suffer_score,
            activity.calories,
            activity.map.summary_polyline if activity.map else None,
            activity.total_elevation_gain,
            activity.average_speed,
            activity.max_speed,
            activity.average_cadence,
            str(activity.type),
            start_latitude,
            start_longitude,
            activity.timezone,
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
    else:
        strava_weather_data = (
            activity.id,
            activity.start_date.isoformat() if activity.start_date else None,
            start_date_local,
            float(activity.distance) / 1000 if activity.distance else None,
            float(activity.elapsed_time) if activity.elapsed_time else None,
            float(activity.moving_time) if activity.moving_time else None,
            activity.max_heartrate,
            activity.average_heartrate,
            activity.suffer_score,
            activity.calories,
            activity.map.summary_polyline if activity.map else None,
            activity.total_elevation_gain,
            activity.average_speed,
            activity.max_speed,
            activity.average_cadence,
            str(activity.type),
            start_latitude,
            start_longitude,
            activity.timezone,
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

    try:
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
        print(f"[DB] Saved activity {activity.id} with weather data")
    except Exception as e:
        print(f"[DB] Error saving activity {activity.id}: {e}")
        conn.rollback()
    print(f"[DB] Completed processing activity {activity.id}")

def fetch_data_from_db(query):
    """Fetches data from the database using the provided query."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()
    return data, columns

def activity_exists(conn, activity_id):
    """Check if an activity already exists in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM strava_activities_weather WHERE id = ?", (activity_id,))
    return cursor.fetchone() is not None

def sync_data(time_range="Last 30 Days"):
    """Syncs data from Strava API for the last 30 days."""
    try:
        # Create database and tables if they don't exist
        create_database_and_tables()

        # Initialize Strava client
        client = authenticate_strava()
        if not client:
            return False, "Failed to authenticate with Strava"
        
        # Set the cutoff date based on the provided time range
        if time_range == "Last 7 Days":
            after_datetime = (datetime.now() - timedelta(days=7)).replace(tzinfo=timezone.utc)
        elif time_range == "Last 30 Days":
            after_datetime = (datetime.now() - timedelta(days=30)).replace(tzinfo=timezone.utc)
        elif time_range == "Last 3 Months":
             after_datetime = (datetime.now() - timedelta(days=90)).replace(tzinfo=timezone.utc)
        else:  # Default to "Last 30 Days"
             after_datetime = (datetime.now() - timedelta(days=30)).replace(tzinfo=timezone.utc)


        # Stream and process activities
        activities_processed = 0
        conn = sqlite3.connect(DATABASE_NAME)
        
        for activity in stream_activities(client, after=after_datetime):
            if activity.type != 'Run':
                continue
                
            # Check if activity already exists
            if activity_exists(conn, activity.id):
                continue
                
            # Get detailed activity data
            detailed_activity = client.get_activity(activity.id)
            if not detailed_activity:
                continue
                
            # Get weather data if location available
            weather_data = None
            air_pollution_data = None
            city_name = None
            
            if detailed_activity.start_latlng:
                # Use start of activity day for weather data
                activity_date = detailed_activity.start_date.date()
                activity_timestamp = int(datetime.combine(activity_date, 
                                                       datetime.min.time()).timestamp())
                
                weather_data, air_pollution_data, city_name = fetch_openweathermap_data(
                    detailed_activity.start_latlng.lat,
                    detailed_activity.start_latlng.lon,
                    activity_timestamp,
                    detailed_activity.elapsed_time
                )
            
            # Store timestamp at start of day
            ist_timestamp = int(datetime.combine(detailed_activity.start_date.date(), 
                                               datetime.min.time()).timestamp())
            
            # Insert data into database
            insert_strava_data(conn, detailed_activity, weather_data, air_pollution_data, 
                             city_name, ist_timestamp)
            activities_processed += 1
            
            # Add delay to respect API rate limits
            # time.sleep(STRAVA_REQUEST_DELAY)
        
        conn.close()

        return True, f"Successfully synced {activities_processed} new activities."
        
    except Exception as e:
        return False, f"Error during sync: {str(e)}"


def calculate_average_metrics(df, period):
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
    return avg_metrics

def fetch_last_7_runs(df):
    """Fetches the last 7 runs from the provided DataFrame."""
    if df.empty:
        return []
    
    df_sorted = df.sort_values(by='start_date_ist', ascending=False).head(7)
    return df_sorted.to_dict(orient='records')


def load_goal():
    """Loads the user's goal from the JSON file."""
    try:
        with open(GOAL_FILE, "r") as f:
            data = json.load(f)
            return data.get("goal", "")
    except FileNotFoundError:
        return ""
    except json.JSONDecodeError:
        return ""

def save_goal(goal):
    """Saves the user's goal to the JSON file."""
    with open(GOAL_FILE, "w") as f:
        json.dump({"goal": goal}, f)

def fetch_last_activity(df):
    """Fetches the last activity from the provided DataFrame."""
    if df.empty:
        return None
    df_sorted = df.sort_values(by='start_date_ist', ascending=False)
    return df_sorted.iloc[0].to_dict()