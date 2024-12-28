import stravalib
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import time
import sqlite3
import google.generativeai as genai

load_dotenv()  # Load environment variables from .env file

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
DATABASE_NAME = "running_coach.db"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_USER_ID = 1

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')


def authenticate_strava():
    """
    Authenticates with the Strava API using OAuth 2.0.
    Returns a Strava client object.
    """
    client = stravalib.Client()

    # Check if we have a refresh token
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
    if refresh_token:
        try:
            print("Refreshing access token...")
            refresh_response = client.refresh_access_token(
                client_id=STRAVA_CLIENT_ID,
                client_secret=STRAVA_CLIENT_SECRET,
                refresh_token=refresh_token
            )
            client.access_token = refresh_response['access_token']
            os.environ["STRAVA_ACCESS_TOKEN"] = client.access_token
            print("Access token refreshed successfully.")
            return client
        except Exception as e:
            print(f"Error refreshing access token: {e}")
            print("Proceeding with new authentication flow.")

    # If no refresh token or refresh failed, start the OAuth flow
    authorize_url = client.authorization_url(
        client_id=STRAVA_CLIENT_ID,
        redirect_uri="http://localhost:8000/authorized",
        scope=["read_all", "activity:read_all"]  # Explicitly request activity:read_all scope
    )
    print(f"Please visit this URL to authorize: {authorize_url}")
    code = input("Enter the authorization code from the URL: ")

    try:
        token_response = client.exchange_code_for_token(
            client_id=STRAVA_CLIENT_ID,
            client_secret=STRAVA_CLIENT_SECRET,
            code=code
        )
        client.access_token = token_response['access_token']
        os.environ["STRAVA_ACCESS_TOKEN"] = client.access_token
        os.environ["STRAVA_REFRESH_TOKEN"] = token_response['refresh_token']
        print("Authentication successful.")
        return client
    except Exception as e:
        print(f"Error during authentication: {e}")
        return None


def create_or_update_database():
    """Creates the SQLite database and defines the schema, or updates if needed."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Check if the activities table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
        table_exists = cursor.fetchone()

        if not table_exists:
            # Create the activities table
            cursor.execute("""
                CREATE TABLE activities (
                    id INTEGER PRIMARY KEY,
                    start_date TEXT,
                    distance REAL,
                    elapsed_time REAL,
                    moving_time REAL,
                    max_heartrate INTEGER,
                    average_heartrate REAL,
                    suffer_score INTEGER,
                    calories REAL,
                    map_summary_polyline TEXT,
                    total_elevation_gain REAL,
                    average_speed REAL,
                    max_speed REAL,
                    average_cadence REAL,
                    type TEXT
                )
            """)
            conn.commit()
            print("Database and activities table created successfully.")
        else:
            print("Database and activities table already exist.")
            # Check if all columns exist
            cursor.execute("PRAGMA table_info(activities)")
            columns = [row[1] for row in cursor.fetchall()]
            required_columns = ["id", "start_date", "distance", "elapsed_time", "moving_time", "max_heartrate", "average_heartrate", "suffer_score", "calories", "map_summary_polyline", "total_elevation_gain", "average_speed", "max_speed", "average_cadence", "type"]
            for column in required_columns:
                if column not in columns:
                    cursor.execute(f"ALTER TABLE activities ADD COLUMN {column} TEXT")
                    conn.commit()
                    print(f"Added column {column} to activities table.")
        
        # Check if the goals table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='goals'")
        goals_table_exists = cursor.fetchone()
        if not goals_table_exists:
            # Create the goals table
            cursor.execute("""
                CREATE TABLE goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    goal_narrative TEXT
                )
            """)
            conn.commit()
            print("Goals table created successfully.")
        else:
            print("Goals table already exists.")
            # Check if goal_narrative column exists
            cursor.execute("PRAGMA table_info(goals)")
            goal_columns = [row[1] for row in cursor.fetchall()]
            if "goal_narrative" not in goal_columns:
                cursor.execute("ALTER TABLE goals ADD COLUMN goal_narrative TEXT")
                conn.commit()
                print("Added column goal_narrative to goals table.")
            
            # Remove old columns if they exist
            if "goal_category" in goal_columns:
                cursor.execute("ALTER TABLE goals DROP COLUMN goal_category")
                conn.commit()
                print("Removed column goal_category from goals table.")
            if "target_value" in goal_columns:
                cursor.execute("ALTER TABLE goals DROP COLUMN target_value")
                conn.commit()
                print("Removed column target_value from goals table.")
    except sqlite3.Error as e:
        print(f"Error creating or updating database: {e}")
    finally:
        if conn:
            conn.close()


def fetch_and_store_activities(client, num_years, user_goals=None):
    """
    Fetches running activities from the Strava API, handles pagination and rate limits,
    and stores the data in the SQLite database.
    """
    activities_fetched = 0
    activities_stored = 0
    current_year = datetime.now().year
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Get the most recent activity start date from the database
        cursor.execute("SELECT start_date FROM activities ORDER BY id DESC LIMIT 1")
        last_activity_row = cursor.fetchone()
        after_date = None
        if last_activity_row and last_activity_row[0]:
            after_date = datetime.fromisoformat(last_activity_row[0])
            print(f"Fetching activities after: {after_date}")
        
        for year_offset in range(num_years):
            year = current_year - year_offset
            print(f"Fetching activities for year: {year}")
            all_activities = client.get_activities()
            for activity_summary in all_activities:
                print(f"  - Activity ID: {activity_summary.id}, Type: {activity_summary.type}, Start Date: {activity_summary.start_date}")
                if activity_summary.type == "Run" and activity_summary.start_date.year == year and (not after_date or activity_summary.start_date > after_date):
                    print(f"Fetching detailed data for activity ID: {activity_summary.id}")
                    # Fetch detailed activity data
                    activity = client.get_activity(activity_summary.id)
                    activities_fetched += 1
                    
                    # Extract relevant fields
                    extracted_activity = {
                        "id": activity.id,
                        "start_date": activity.start_date.isoformat() if activity.start_date else None,
                        "distance": float(activity.distance) / 1000 if activity.distance else None,
                        "elapsed_time": float(activity.elapsed_time) if activity.elapsed_time else None,
                        "moving_time": float(activity.moving_time) if activity.moving_time else None,
                        "max_heartrate": activity.max_heartrate,
                        "average_heartrate": activity.average_heartrate,
                        "suffer_score": activity.suffer_score,
                        "calories": activity.calories,
                        "map_summary_polyline": activity.map.summary_polyline if activity.map else None,
                        "total_elevation_gain": activity.total_elevation_gain,
                        "average_speed": activity.average_speed,
                        "max_speed": activity.max_speed,
                        "average_cadence": activity.average_cadence,
                        "type": str(activity.type),
                    }
                    
                    # Insert data into the database
                    cursor.execute("""
                        INSERT INTO activities (id, start_date, distance, elapsed_time, moving_time, max_heartrate, average_heartrate, suffer_score, calories, map_summary_polyline, total_elevation_gain, average_speed, max_speed, average_cadence, type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        extracted_activity["id"],
                        extracted_activity["start_date"],
                        extracted_activity["distance"],
                        extracted_activity["elapsed_time"],
                        extracted_activity["moving_time"],
                        extracted_activity["max_heartrate"],
                        extracted_activity["average_heartrate"],
                        extracted_activity["suffer_score"],
                        extracted_activity["calories"],
                        extracted_activity["map_summary_polyline"],
                        extracted_activity["total_elevation_gain"],
                        extracted_activity["average_speed"],
                        extracted_activity["max_speed"],
                        extracted_activity["average_cadence"],
                        extracted_activity["type"]
                    ))
                    conn.commit()
                    activities_stored += 1
                    print(f"  - Fetched: {activities_fetched}, Stored: {activities_stored}", end='\r')
                elif activity_summary.start_date.year < year:
                    print(f"Reached activities outside of {year}. Stopping fetch for this year.")
                    break
                
                # Implement a basic rate limiter (adjust as needed)
                time.sleep(0.1)  # Wait for 0.1 seconds between API calls
                
                # Check rate limits
                if hasattr(all_activities, 'response') and all_activities.response:
                    rate_limit_header = all_activities.response.headers.get('X-RateLimit-Limit')
                    rate_limit_usage_header = all_activities.response.headers.get('X-RateLimit-Usage')
                    if rate_limit_header and rate_limit_usage_header:
                        rate_limit = int(rate_limit_header)
                        rate_limit_usage = int(rate_limit_usage_header)
                        remaining_limit = rate_limit - rate_limit_usage
                        print(f"Rate Limit: {rate_limit}, Usage: {rate_limit_usage}, Remaining: {remaining_limit}")
                        if remaining_limit < 10:
                            print("Approaching API limit. Waiting for 60 seconds.")
                            time.sleep(60)
        
        if user_goals:
            cursor.execute("""
                INSERT INTO goals (user_id, goal_narrative)
                VALUES (?, ?)
            """, (DEFAULT_USER_ID, user_goals))
            conn.commit()
            print("User goals stored in the database.")
        
        print(f"\nFetched {activities_fetched} running activities and stored {activities_stored} in the database.")
    except sqlite3.Error as e:
        print(f"Error storing activities: {e}")
    except Exception as e:
        print(f"Error fetching activities: {e}")
    finally:
        if conn:
            conn.close()


def get_last_activity():
    """
    Retrieves the last inserted activity from the database.
    Returns a dictionary representing the activity.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activities ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            activity = dict(zip(columns, row))
            return activity
        else:
            return None
    except sqlite3.Error as e:
        print(f"Error retrieving last activity: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_user_goals():
    """
    Retrieves the user's goals from the database.
    Returns a dictionary representing the goals.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT goal_narrative FROM goals WHERE user_id = ? ORDER BY id DESC LIMIT 1", (DEFAULT_USER_ID,))
        row = cursor.fetchone()
        if row:
            return row[0]
        else:
            return None
    except sqlite3.Error as e:
        print(f"Error retrieving user goals: {e}")
        return None
    finally:
        if conn:
            conn.close()


def generate_gemini_prompt(activity):
    """Generates a prompt for the Gemini API based on the activity data and user goals."""
    user_goals = get_user_goals()
    prompt = f"""
    Analyze this run data:
    Distance: {activity.get('distance', 'N/A')} km
    Elapsed Time: {activity.get('elapsed_time', 'N/A')} seconds
    Average Pace: {activity.get('elapsed_time', 0) / activity.get('distance', 1) / 60:.2f} min/km
    Average Heart Rate: {activity.get('average_heartrate', 'N/A')} bpm
    Suffer Score: {activity.get('suffer_score', 'N/A')}
    Calories: {activity.get('calories', 'N/A')}
    
    """
    if user_goals:
        prompt += f"The user's goal is: {user_goals}\n"
    
    prompt += "Provide feedback on pace consistency and how this run contributes to their goals."
    return prompt


def get_gemini_response(prompt):
    """Sends the prompt to the Gemini API and returns the response."""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error getting Gemini response: {e}")
        return "Error getting Gemini response."