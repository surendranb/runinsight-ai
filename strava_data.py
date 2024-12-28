import stravalib
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import numpy as np
import time
import sqlite3
import google.generativeai as genai
from collections import defaultdict

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
                if activity_summary.type == "Run" and activity_summary.start_date.year == year:
                    
                    # Check if activity already exists in the database
                    cursor.execute("SELECT id FROM activities WHERE id = ?", (activity_summary.id,))
                    existing_activity = cursor.fetchone()
                    if existing_activity:
                        print(f"Skipping activity ID: {activity_summary.id} (already in database)")
                        continue
                    
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
                else:
                    time.sleep(0.1) # Wait for 0.1 seconds between API calls
        
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


def get_activity_paces(activity_id):
    """
    Calculates the pace at different points during the run.
    Returns a dictionary with "time" and "pace" keys.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT elapsed_time, distance FROM activities WHERE id = ?", (activity_id,))
        row = cursor.fetchone()
        if row:
            elapsed_time = row[0]
            distance = row[1]
            if elapsed_time and distance:
                pace = elapsed_time / distance / 60
                return {"time": [0], "pace": [pace]}
            else:
                return {"time": [], "pace": []}
        else:
            return {"time": [], "pace": []}
    except sqlite3.Error as e:
        print(f"Error retrieving activity paces: {e}")
        return {"time": [], "pace": []}
    finally:
        if conn:
            conn.close()


def get_progress_summary():
    """
    Retrieves a summary of the user's progress for different time periods.
    Returns a dictionary where keys are time periods and values are dictionaries of metrics.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        time_periods = {
            "Last 7 days": datetime.now() - timedelta(days=7),
            "Last 30 days": datetime.now() - timedelta(days=30),
            "Last 90 days": datetime.now() - timedelta(days=90),
            "This year": datetime(datetime.now().year, 1, 1),
            "Last year": datetime(datetime.now().year - 1, 1, 1),
            "Overall": None
        }
        
        progress_data = {}
        for period_name, start_date in time_periods.items():
            
            if start_date:
                cursor.execute("SELECT * FROM activities WHERE start_date >= ?", (start_date.isoformat(),))
                activities = cursor.fetchall()
            else:
                cursor.execute("SELECT * FROM activities")
                activities = cursor.fetchall()
            
            best_5k = 0
            best_10k = 0

            if activities:
                
                # Longest Run
                distances = [row[2] for row in activities if row[2]]
                longest_run = max(distances) if distances else 0
                
                # Fastest Pace
                valid_paces = [row[4] / row[2] / 60 for row in activities if row[2] and row[4] and (row[4] / row[2] / 60) >= 7]  # Filter out paces < 7 min/km
                fastest_pace = min(valid_paces) if valid_paces else 0  # Handle empty list

                # Average Pace (Filtered)
                filtered_activities_for_average_pace = [row for row in activities if row[2] and row[4] and (row[4] / row[2] / 60) >= 7] # Filter out unrealistic entries
                total_moving_time = sum(row[4] for row in filtered_activities_for_average_pace if row[4])
                total_distance = sum(row[2] for row in filtered_activities_for_average_pace if row[2])
                average_pace = (total_moving_time / total_distance / 60) if total_distance else 0
        
                # Pace Variability (Standard Deviation of pace)               
                valid_paces = [row[4] / row[2] / 60 for row in activities if row[2] and row[4] and (row[4] / row[2] / 60) >= 7]  # Filter for valid paces here as well.
                pace_variability = np.std(valid_paces) if valid_paces else 0

                # Total Distance
                total_distance = sum([row[2] for row in activities if row[2]])

                # Average Runs per Week
                start_dates = [datetime.fromisoformat(row[1]) for row in activities]
                if start_dates:
                    first_date = min(start_dates)
                    last_date = max(start_dates)
                    days_diff = (last_date - first_date).days
                    weeks_diff = days_diff / 7 if days_diff > 0 else 0
                    average_runs_per_week = len(activities) / weeks_diff if weeks_diff > 0 else 0
                else:
                    average_runs_per_week = 0
                
                # Average Heart Rate
                heart_rates = [row[6] for row in activities if row[6]]
                average_heart_rate = sum(heart_rates) / len(heart_rates) if heart_rates else 0
                
                five_k_activities = [act for act in activities if 4.8 <= act[2] <= 5.2 and act[4]/act[2]/60 >= 7]
                ten_k_activities = [act for act in activities if 9.8 <= act[2] <= 10.2 and act[4]/act[2]/60 >= 7]

                if five_k_activities:
                    best_5k = min([act[4] / act[2] / 60 for act in five_k_activities if act[2] and act[4]]) if five_k_activities else 0
                if ten_k_activities:
                    best_10k = min([act[4] / act[2] / 60 for act in ten_k_activities if act[2] and act[4]]) if ten_k_activities else 0



                progress_data[period_name] = {
                    "longest_run": longest_run,
                    "fastest_pace": fastest_pace,
                    "average_pace": average_pace,
                    "total_distance": total_distance,
                    "average_runs_per_week": average_runs_per_week,
                    "average_heart_rate": average_heart_rate,
                    "pace_variability": pace_variability,
                    "best_5k": best_5k,
                    "best_10k": best_10k
                }
            else:
                progress_data[period_name] = {
                    "longest_run": 0,
                    "fastest_pace": 0,
                    "average_pace": 0,
                    "total_distance": 0,
                    "average_runs_per_week": 0,
                    "average_heart_rate": 0,
                    "pace_variability": 0
                }
            
        return progress_data
    except sqlite3.Error as e:
        print(f"Error retrieving progress summary: {e}")
        return {}
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

def generate_gemini_prompt_with_details(recent_runs, user_goals):
    """Generates a detailed prompt with aggregated statistics."""

    num_runs = len(recent_runs)
    total_distance = sum(run[2] for run in recent_runs if run[2])
    total_moving_time = sum(run[4] for run in recent_runs if run[4])
    average_pace = (total_moving_time / total_distance / 60) if total_distance else 0

    # Initialize lists to store individual run data
    distances = []
    moving_times = []
    average_paces = []
    average_heart_rates = []
    max_heart_rates = []


    for run in recent_runs:
        distance = run[2]
        moving_time = run[4]
        avg_hr = run[6]
        max_hr = run[5]

        if distance and moving_time:
            distances.append(distance)
            moving_times.append(moving_time)
            average_paces.append(moving_time / distance / 60)
        if avg_hr:
            average_heart_rates.append(avg_hr)
        if max_hr:
            max_heart_rates.append(max_hr)


    pace_variability = np.std(average_paces) if average_paces else 0
    avg_heart_rate = np.mean(average_heart_rates) if average_heart_rates else 0
    max_heart_rate = max(max_heart_rates) if max_heart_rates else 0  # Use max for max_heart_rate


    prompt = f"""Analyze recent run data (last 30 days) for a runner:\n\n"""

    prompt += f"Number of Runs: {num_runs}\n"
    prompt += f"Total Distance: {total_distance:.2f} km\n"
    prompt += f"Average Pace: {average_pace:.2f} min/km\n"
    prompt += f"Pace Variability: {pace_variability:.2f} min/km\n"
    prompt += f"Average Heart Rate: {avg_heart_rate:.2f} bpm\n"
    prompt += f"Max Heart Rate: {max_heart_rate:.2f} bpm\n"


    # Add more detailed metrics or insights here if available


    if user_goals:
        prompt += f"\nThe user's goal is: {user_goals}\n\n"

    prompt += f"Provide specific and detailed feedback on the runner's overall performance, considering aspects such as pace consistency, training volume, heart rate trends, and progress towards goals. Suggest actionable advice for improvement, using the provided data. Do not give generic feedback."

    return prompt



def get_gemini_response(prompt):
    """Sends the prompt to the Gemini API and returns the response."""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error getting Gemini response: {e}")
        return "Error getting Gemini response."