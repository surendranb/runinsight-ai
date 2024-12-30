# strava_api.py
import stravalib
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import sqlite3
import json

load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
DATABASE_NAME = "running_coach.db"
REDIRECT_URI = "http://localhost:8000/authorized"

def authenticate_strava():
    """Authenticates with the Strava API using OAuth 2.0."""
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
        redirect_uri=REDIRECT_URI,
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

def exchange_code_for_token(client, code):
    """Exchanges the authorization code for an access token."""
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
        print(f"Error during token exchange: {e}")
        return None

def fetch_activities(client, limit=None):
    """Fetches running activities from the Strava API for the current year."""
    activities_fetched = 0
    all_activities_data = []
    current_year = datetime.now().year
    
    request_count = 0
    window_start_time = None
    
    all_activities = client.get_activities()
    for activity_summary in all_activities:
        if limit and activities_fetched >= limit:
            print(f"Reached limit of {limit} activities. Stopping fetch.")
            break
        if activity_summary.type == "Run" and activity_summary.start_date.year == current_year:
            
            print(f"Fetching detailed data for activity ID: {activity_summary.id}")
            activity = client.get_activity(activity_summary.id)
            activities_fetched += 1
            
            if activity.start_latlng:
                start_latitude = activity.start_latlng.lat
                start_longitude = activity.start_latlng.lon
            else:
                start_latitude = None
                start_longitude = None
            
            extracted_activity = {
                "id": activity.id,
                "start_date": activity.start_date.isoformat() if activity.start_date else None,
                "start_date_local": activity.start_date_local.isoformat() if activity.start_date_local else None,
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
                "start_latitude": start_latitude,
                "start_longitude": start_longitude,
                "timezone": activity.timezone,
                "gear_id": activity.gear_id,
                "device_name": activity.device_name,
                "splits_metric": json.dumps([split.to_dict() for split in activity.splits_metric]) if activity.splits_metric else None,
                "best_efforts": json.dumps([effort.to_dict() for effort in activity.best_efforts]) if activity.best_efforts else None
            }
            all_activities_data.append(extracted_activity)
            print(f"  - Fetched: {activities_fetched}", end='\r')
            
            time.sleep(10) # Fixed 10-second delay
        elif activity_summary.start_date.year < current_year:
            print(f"Reached activities outside of {current_year}. Stopping fetch.")
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
    print(f"\nFetched {activities_fetched} running activities.")
    return all_activities_data