import os
from datetime import datetime, timezone
import stravalib
import requests
from dotenv import load_dotenv
import time

load_dotenv()

class DataFetcher:
    def __init__(self):
        self.strava_client_id = os.getenv("STRAVA_CLIENT_ID")
        self.strava_client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.strava_refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self.weather_api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        self.client = None

    def authenticate_strava(self):
        """Authenticate with Strava using refresh token"""
        self.client = stravalib.Client()
        
        try:
            refresh_response = self.client.refresh_access_token(
                client_id=self.strava_client_id,
                client_secret=self.strava_client_secret,
                refresh_token=self.strava_refresh_token
            )
            self.client.access_token = refresh_response['access_token']
            return True
        except Exception as e:
            print(f"Authentication error: {e}")
            return False

    def fetch_activities(self, after_date=None):
        """Fetch activities from Strava"""
        if not self.client:
            if not self.authenticate_strava():
                return []

        activities = []
        try:
            for activity in self.client.get_activities(after=after_date):
                if activity.type != 'Run':
                    continue
                
                # Get detailed activity data
                detailed_activity = self.client.get_activity(activity.id)
                time.sleep(2)  # Rate limiting
                
                # Get weather and pollution data if location available
                weather_data = None
                pollution_data = None
                if detailed_activity.start_latlng:
                    timestamp = int(detailed_activity.start_date.timestamp())
                    weather_data = self.fetch_weather_data(
                        detailed_activity.start_latlng.lat,
                        detailed_activity.start_latlng.lon,
                        timestamp
                    )
                    pollution_data = self.fetch_air_quality(
                        detailed_activity.start_latlng.lat,
                        detailed_activity.start_latlng.lon,
                        timestamp,
                        int(detailed_activity.elapsed_time.total_seconds())
                    )
                
                activities.append({
                    'strava_data': detailed_activity,
                    'weather_data': weather_data,
                    'pollution_data': pollution_data
                })
        
        except Exception as e:
            print(f"Error fetching activities: {e}")
        
        return activities

    def fetch_weather_data(self, lat, lon, timestamp):
        """Fetch historical weather data"""
        url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
        params = {
            "lat": lat,
            "lon": lon,
            "dt": timestamp,
            "appid": self.weather_api_key,
            "units": "metric"
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching weather data: {e}")
            return None

    def fetch_air_quality(self, lat, lon, start_timestamp, duration):
        """Fetch air quality data"""
        url = "http://api.openweathermap.org/data/2.5/air_pollution/history"
        end_timestamp = start_timestamp + duration
        
        params = {
            "lat": lat,
            "lon": lon,
            "start": start_timestamp,
            "end": end_timestamp,
            "appid": self.weather_api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching air quality data: {e}")
            return None