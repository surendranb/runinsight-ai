import streamlit as st
import pandas as pd
import sqlite3, time
from datetime import datetime, timedelta, timezone
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from api_client import authenticate_strava,fetch_openweathermap_data, stream_activities
from database import activity_exists, insert_strava_data

# --- Database Connection and Data Fetching ---
def fetch_data_from_db(query):
    """Fetches data from the database using the provided query."""
    conn = sqlite3.connect("ai_running_coach.db")
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()
    return pd.DataFrame(data, columns=columns)

# --- Data Preparation ---
def prepare_data():
    """Fetches data from the database and prepares it for analysis."""
    strava_query = "SELECT id, start_date_ist, distance, elapsed_time, moving_time, average_speed, max_speed, average_heartrate, max_heartrate, suffer_score, calories, total_elevation_gain, average_cadence, temperature, feels_like, humidity, weather_conditions, pollution_aqi, pollution_pm25, city_name FROM strava_activities_weather"
    splits_query = "SELECT activity_id, split, distance, elapsed_time, average_speed, elevation_difference, moving_time, average_heartrate, average_grade_adjusted_speed FROM splits_data"
    best_efforts_query = "SELECT activity_id, name, distance, elapsed_time, start_date FROM best_efforts_data"

    strava_df = fetch_data_from_db(strava_query)
    splits_df = fetch_data_from_db(splits_query)
    best_efforts_df = fetch_data_from_db(best_efforts_query)

    # Convert start_date_ist to numeric, coercing errors to NaN
    strava_df['start_date_ist'] = pd.to_numeric(strava_df['start_date_ist'], errors='coerce')
    
    # Drop rows where start_date_ist is NaN
    strava_df.dropna(subset=['start_date_ist'], inplace=True)

    # Convert start_date_ist to datetime
    strava_df['start_date_ist'] = pd.to_datetime(strava_df['start_date_ist'], unit='s')
    
    # Convert other columns to numeric where applicable
    numeric_cols = ['distance', 'elapsed_time', 'moving_time', 'average_speed', 'max_speed', 'average_heartrate', 'max_heartrate', 'suffer_score', 'calories', 'total_elevation_gain', 'average_cadence', 'temperature', 'feels_like', 'humidity', 'pollution_aqi', 'pollution_pm25']
    for col in numeric_cols:
        if col in strava_df.columns:
            strava_df[col] = pd.to_numeric(strava_df[col], errors='coerce')
    
    numeric_cols_splits = ['distance', 'elapsed_time', 'average_speed', 'elevation_difference', 'moving_time', 'average_heartrate', 'average_grade_adjusted_speed']
    for col in numeric_cols_splits:
        if col in splits_df.columns:
            splits_df[col] = pd.to_numeric(splits_df[col], errors='coerce')
    
    numeric_cols_best_efforts = ['distance', 'elapsed_time']
    for col in numeric_cols_best_efforts:
        if col in best_efforts_df.columns:
            best_efforts_df[col] = pd.to_numeric(best_efforts_df[col], errors='coerce')
    
    best_efforts_df['start_date'] = pd.to_datetime(best_efforts_df['start_date'], errors='coerce')

    return strava_df, splits_df, best_efforts_df
# --- Metric Calculation Functions ---
def calculate_metric(df, metric, period):
    """Calculates a metric for a given period."""
    now = datetime.now()
    if period == "Last 7 Days":
        cutoff = now - timedelta(days=7)
    elif period == "Last 30 Days":
        cutoff = now - timedelta(days=30)
    elif period == "Last 90 Days":
        cutoff = now - timedelta(days=90)
    elif period == "Year-to-Date":
        cutoff = datetime(now.year, 1, 1)
    elif period == "Last Year":
        cutoff = datetime(now.year - 1, 1, 1)
    else: # Overall
        cutoff = datetime.min

    filtered_df = df[df['start_date_ist'] >= cutoff] if 'start_date_ist' in df.columns else df[df['start_date'] >= cutoff] if 'start_date' in df.columns else df
    
    if filtered_df.empty:
        return None, None, None, None, None
    
    if 'start_date_ist' in filtered_df.columns:
        daily_data = filtered_df.groupby(filtered_df['start_date_ist'].dt.date)
    elif 'start_date' in filtered_df.columns:
        daily_data = filtered_df.groupby(filtered_df['start_date'].dt.date)
    else:
        return None, None, None, None, None
    
    if metric == "Average Pace":
        def avg_pace(x):
            total_distance = x['distance'].sum()
            total_time = x['elapsed_time'].sum()
            if total_distance > 0 and total_time > 0:
                avg_pace_seconds_per_km = (total_time / total_distance)
                avg_pace_minutes_per_km = avg_pace_seconds_per_km / 60
                return avg_pace_minutes_per_km
            else:
                return None
        daily_avg_paces = daily_data.apply(avg_pace).dropna()
        if not daily_avg_paces.empty:
            avg_pace_minutes_per_km = daily_avg_paces.mean()
            median_pace_minutes_per_km = daily_avg_paces.median()
            return round(avg_pace_minutes_per_km, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_pace_minutes_per_km, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Average Heart Rate":
        daily_avg_heartrates = daily_data['average_heartrate'].mean().dropna()
        if not daily_avg_heartrates.empty:
            avg_heartrate = daily_avg_heartrates.mean()
            median_heartrate = daily_avg_heartrates.median()
            return round(avg_heartrate, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_heartrate, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Distance":
        daily_distances = daily_data['distance'].sum().dropna()
        if not daily_distances.empty:
            avg_distance = daily_distances.mean()
            median_distance = daily_distances.median()
            return round(avg_distance, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_distance, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Max Speed":
        def max_speed_km_hr(x):
            max_speed = x['max_speed'].max()
            return max_speed if max_speed is not None else None
        daily_max_speeds = daily_data.apply(max_speed_km_hr).dropna()
        if not daily_max_speeds.empty:
            avg_max_speed = daily_max_speeds.mean()
            median_max_speed = daily_max_speeds.median()
            return round(avg_max_speed, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_max_speed, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Total Elevation Gain":
        daily_elevation_gains = daily_data['total_elevation_gain'].mean().dropna()
        if not daily_elevation_gains.empty:
            avg_elevation_gain = daily_elevation_gains.mean()
            median_elevation_gain = daily_elevation_gains.median()
            return round(avg_elevation_gain, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_elevation_gain, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Average Cadence":
        daily_avg_cadences = daily_data['average_cadence'].mean().dropna()
        if not daily_avg_cadences.empty:
            avg_cadence = daily_avg_cadences.mean()
            median_cadence = daily_avg_cadences.median()
            return round(avg_cadence, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_cadence, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Calories Burned":
        daily_calories = daily_data['calories'].mean().dropna()
        if not daily_calories.empty:
            avg_calories = daily_calories.mean()
            median_calories = daily_calories.median()
            return round(avg_calories, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_calories, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Suffer Score":
        daily_suffer_scores = daily_data['suffer_score'].mean().dropna()
        if not daily_suffer_scores.empty:
            avg_suffer_score = daily_suffer_scores.mean()
            median_suffer_score = daily_suffer_scores.median()
            return round(avg_suffer_score, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_suffer_score, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Temperature":
        daily_temperatures = daily_data['temperature'].mean().dropna()
        if not daily_temperatures.empty:
            avg_temperature = daily_temperatures.mean()
            median_temperature = daily_temperatures.median()
            return round(avg_temperature, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_temperature, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Feels Like Temperature":
        daily_feels_like_temperatures = daily_data['feels_like'].mean().dropna()
        if not daily_feels_like_temperatures.empty:
            avg_feels_like_temperature = daily_feels_like_temperatures.mean()
            median_feels_like_temperature = daily_feels_like_temperatures.median()
            return round(avg_feels_like_temperature, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_feels_like_temperature, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Humidity":
        daily_humidities = daily_data['humidity'].mean().dropna()
        if not daily_humidities.empty:
            avg_humidity = daily_humidities.mean()
            median_humidity = daily_humidities.median()
            return round(avg_humidity, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_humidity, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Pollution PM2.5":
        daily_pm25 = daily_data['pollution_pm25'].mean().dropna()
        if not daily_pm25.empty:
            avg_pm25 = daily_pm25.mean()
            median_pm25 = daily_pm25.median()
            return round(avg_pm25, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_pm25, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    elif metric == "Pollution AQI":
        daily_aqi = daily_data['pollution_aqi'].mean().dropna()
        if not daily_aqi.empty:
            avg_aqi = daily_aqi.mean()
            median_aqi = daily_aqi.median()
            return round(avg_aqi, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], round(median_aqi, 2), filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date'], filtered_df['start_date_ist'] if 'start_date_ist' in filtered_df.columns else filtered_df['start_date']
        else:
            return None, None, None, None, None
    else:
        return None, None, None, None, None

def calculate_percentage_change(current, previous):
    """Calculates the percentage change between two values."""
    if previous is None or previous == 0:
        return None
    if current is None:
        return None
    return ((current - previous) / previous) * 100

def get_previous_period(period):
    """Gets the previous period for comparison."""
    if period == "Last 7 Days":
        return "Last 14 Days"
    elif period == "Last 30 Days":
        return "Last 60 Days"
    elif period == "Last 90 Days":
        return "Last 180 Days"
    elif period == "Year-to-Date":
        return "Last Year"
    elif period == "Last Year":
        return "Previous Year"
    else:
        return None

def get_trend_data(df, metric, period):
    """Gets the trend data for a metric over a period."""
    now = datetime.now()
    if period == "Last 7 Days":
        cutoff = now - timedelta(days=7)
    elif period == "Last 30 Days":
        cutoff = now - timedelta(days=30)
    elif period == "Last 90 Days":
        cutoff = now - timedelta(days=90)
    elif period == "Year-to-Date":
        cutoff = datetime(now.year, 1, 1)
    elif period == "Last Year":
        cutoff = datetime(now.year - 1, 1, 1)
    else:  # Overall
        cutoff = datetime.min
    
    filtered_df = df[df['start_date_ist'] >= cutoff] if 'start_date_ist' in df.columns else df[df['start_date'] >= cutoff] if 'start_date' in df.columns else df
    
    if filtered_df.empty:
        return pd.DataFrame()
    
    if 'start_date_ist' in filtered_df.columns:
        date_column = 'start_date_ist'
    elif 'start_date' in filtered_df.columns:
        date_column = 'start_date'
    else:
        return pd.DataFrame()
        
    filtered_df = filtered_df.sort_values(by=date_column)
    
    # Group by date and calculate the appropriate metric
    if metric == "Average Pace":
        filtered_df['pace'] = filtered_df['elapsed_time'] / filtered_df['distance']
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['pace'].mean()
    elif metric == "Average Heart Rate":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['average_heartrate'].mean()
    elif metric == "Distance":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['distance'].sum()
    elif metric == "Max Speed":
        filtered_df['max_speed_km_hr'] = filtered_df['max_speed']
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['max_speed_km_hr'].max()
    elif metric == "Total Elevation Gain":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['total_elevation_gain'].mean()
    elif metric == "Average Cadence":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['average_cadence'].mean()
    elif metric == "Calories Burned":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['calories'].mean()
    elif metric == "Suffer Score":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['suffer_score'].mean()
    elif metric == "Temperature":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['temperature'].mean()
    elif metric == "Feels Like Temperature":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['feels_like'].mean()
    elif metric == "Humidity":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['humidity'].mean()
    elif metric == "Pollution PM2.5":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['pollution_pm25'].mean()
    elif metric == "Pollution AQI":
        daily_data = filtered_df.groupby(filtered_df[date_column].dt.date)['pollution_aqi'].mean()
    else:
        return pd.DataFrame()
    
    # Convert the daily_data Series to a DataFrame with datetime index
    daily_df = daily_data.to_frame()
    daily_df.index = pd.to_datetime(daily_df.index)
    
    # Remove zeros
    daily_df = daily_df[daily_df.iloc[:, 0] != 0]
    
    return daily_df

# Calculate pace variation for a single activity

def calculate_pace_variation(splits_df, activity_id):
    """Calculate pace variation for a single activity using splits data."""
    activity_splits = splits_df[splits_df['activity_id'] == activity_id]
    if activity_splits.empty:
        return None
    
    # Calculate pace for each split (seconds per kilometer)
    activity_splits['pace'] = activity_splits['elapsed_time'] / activity_splits['distance']
    return activity_splits['pace'].std()

# Calculate heart rate zones for a single activity

def calculate_heart_rate_zones(strava_df, row):
    """Calculate time spent in different heart rate zones for an activity."""
    if pd.isna(row['average_heartrate']) or pd.isna(row['max_heartrate']):
        return None
    
    # Define heart rate zones based on max heart rate
    max_hr = row['max_heartrate']
    zones = {
        'Easy': (0.6 * max_hr, 0.7 * max_hr),
        'Moderate': (0.7 * max_hr, 0.8 * max_hr),
        'Hard': (0.8 * max_hr, 0.9 * max_hr),
        'Very Hard': (0.9 * max_hr, float('inf'))
    }
    
    # Categorize average heart rate into a zone
    avg_hr = row['average_heartrate']
    for zone_name, (min_hr, max_hr) in zones.items():
        if min_hr <= avg_hr < max_hr:
            return zone_name
    return None

# Calculate running consistency over a period

def calculate_running_consistency(strava_df, period):
    """Calculate number of runs per week over the specified period."""
    now = datetime.now()
    if period == "Last 7 Days":
        cutoff = now - timedelta(days=7)
    elif period == "Last 30 Days":
        cutoff = now - timedelta(days=30)
    elif period == "Last 90 Days":
        cutoff = now - timedelta(days=90)
    else:
        cutoff = datetime(now.year, 1, 1)
    
    filtered_df = strava_df[strava_df['start_date_ist'] >= cutoff].copy()
    filtered_df['week'] = filtered_df['start_date_ist'].dt.isocalendar().week
    weekly_runs = filtered_df.groupby('week').size()
    return weekly_runs.mean(), weekly_runs.std()

# Calculate grade adjusted pace metrics

def calculate_grade_adjusted_metrics(splits_df, strava_df):
    """Calculate grade adjusted pace metrics."""
    if splits_df.empty or 'average_grade_adjusted_speed' not in splits_df.columns:
        return {
            'mean_gap': None,
            'median_gap': None,
            'std_gap': None
        }
        
    # Filter out zero or NaN values in average_grade_adjusted_speed
    valid_splits = splits_df[
        (splits_df['average_grade_adjusted_speed'] > 0) & 
        (splits_df['average_grade_adjusted_speed'].notna())
    ]
    
    if valid_splits.empty:
        return {
            'mean_gap': None,
            'median_gap': None,
            'std_gap': None
        }
    
    valid_splits['grade_adjusted_pace'] = 1000 / valid_splits['average_grade_adjusted_speed']
    
    metrics = {
        'mean_gap': valid_splits['grade_adjusted_pace'].mean(),
        'median_gap': valid_splits['grade_adjusted_pace'].median(),
        'std_gap': valid_splits['grade_adjusted_pace'].std()
    }
    return metrics

# Calculate weekly metrics

def calculate_weekly_metrics(strava_df, splits_df):
    """Calculate metrics aggregated by week."""
    # Ensure we have datetime index
    strava_df = strava_df.copy()
    strava_df['week'] = strava_df['start_date_ist'].dt.strftime('%Y-%W')
    splits_df = splits_df.copy()
    
    # 1. Pace Variation by Week
    pace_variations = []
    for activity_id in strava_df['id'].unique():
        activity_splits = splits_df[splits_df['activity_id'] == activity_id]
        if not activity_splits.empty:
            activity_splits['pace'] = activity_splits['elapsed_time'] / activity_splits['distance']
            variation = activity_splits['pace'].std()
            if variation is not None and not pd.isna(variation):
                activity_date = strava_df[strava_df['id'] == activity_id]['start_date_ist'].iloc[0]
                pace_variations.append({
                    'week': activity_date.strftime('%Y-%W'),
                    'variation': variation
                })
    
    weekly_pace_variation = pd.DataFrame(pace_variations)
    if not weekly_pace_variation.empty:
        weekly_pace_variation = weekly_pace_variation.groupby('week')['variation'].mean().reset_index()
        weekly_pace_variation['week'] = pd.to_datetime(weekly_pace_variation['week'].apply(
            lambda x: f"{x}-1"), format='%Y-%W-%w')
    
    # 2. Heart Rate Zones by Week
    weekly_hr_zones = []
    for _, row in strava_df.iterrows():
        zone = calculate_heart_rate_zones(strava_df, row)
        if zone:
            weekly_hr_zones.append({
                'week': row['start_date_ist'].strftime('%Y-%W'),
                'zone': zone
            })
    
    hr_zones_df = pd.DataFrame(weekly_hr_zones)
    if not hr_zones_df.empty:
        hr_zones_pivot = pd.crosstab(hr_zones_df['week'], hr_zones_df['zone'], normalize='index') * 100
        hr_zones_pivot.index = pd.to_datetime(hr_zones_pivot.index.map(lambda x: f"{x}-1"), format='%Y-%W-%w')
    else:
        hr_zones_pivot = pd.DataFrame()
    
    # 3. Running Consistency (runs per week)
    weekly_runs = strava_df.groupby('week').size().reset_index()
    weekly_runs.columns = ['week', 'num_runs']
    weekly_runs['week'] = pd.to_datetime(weekly_runs['week'].apply(lambda x: f"{x}-1"), format='%Y-%W-%w')
    
    # 4. Grade Adjusted Pace by Week
    splits_df['week'] = pd.to_datetime(splits_df['activity_id'].map(
        strava_df.set_index('id')['start_date_ist'])).dt.strftime('%Y-%W')
    
    weekly_gap = splits_df[splits_df['average_grade_adjusted_speed'] > 0].groupby('week').agg({
        'average_grade_adjusted_speed': lambda x: 1000 / x.mean()  # Convert to pace
    }).reset_index()
    
    weekly_gap['week'] = pd.to_datetime(weekly_gap['week'].apply(lambda x: f"{x}-1"), format='%Y-%W-%w')
    
    return weekly_pace_variation, hr_zones_pivot, weekly_runs, weekly_gap

def calculate_location_metrics(strava_df):
    """Calculate performance metrics grouped by city."""
    # print("Input DataFrame (strava_df):")
    # print(strava_df.head())  # Debug log to check the input DataFrame

    location_metrics = strava_df.groupby('city_name').agg({
        'distance': 'mean',
        'average_heartrate': 'mean',
        'temperature': 'mean',
        'pollution_aqi': 'mean',
        'pollution_pm25': 'mean',
        'total_elevation_gain': 'mean',
        'average_speed': 'mean',
        'id': 'count',  # Number of runs in each city
        'start_date_ist': 'first' #Include Start Date for each run
    }).reset_index()
    
    # Calculate average pace (min/km)
    location_metrics['average_pace'] = 1000 / (location_metrics['average_speed'] * 60)
    
    # Normalize metrics for radar chart
    metrics_to_normalize = ['distance', 'average_heartrate', 'temperature', 
                          'pollution_aqi', 'total_elevation_gain', 'average_pace']
    
    for metric in metrics_to_normalize:
        max_val = location_metrics[metric].max()
        min_val = location_metrics[metric].min()
        if max_val != min_val:
            location_metrics[f'{metric}_normalized'] = (location_metrics[metric] - min_val) / (max_val - min_val)
        else:
            location_metrics[f'{metric}_normalized'] = 1
    # print("Normalized Location Metrics:")
    # print(location_metrics[[f'{metric}_normalized' for metric in metrics_to_normalize]])
    # print(location_metrics)# Debug log to check output DataFrame
    return location_metrics

def calculate_environmental_impact(strava_df):
    """Calculate environmental impact on running performance."""
    df = strava_df.copy()
    
    # Filter out any rows with missing values in key columns
    required_columns = ['temperature', 'humidity', 'pollution_aqi', 'pollution_pm25', 
                       'distance', 'elapsed_time', 'average_speed']
    df = df.dropna(subset=required_columns)
    
    # Basic performance calculations
    df['pace_min_km'] = 1000 / (df['average_speed'] * 60)
    
    # Normalize environmental factors (0-1 scale)
    env_factors = ['temperature', 'humidity', 'pollution_aqi', 'pollution_pm25']
    for factor in env_factors:
        max_val = df[factor].max()
        min_val = df[factor].min()
        if max_val != min_val:
            df[f'{factor}_normalized'] = (df[factor] - min_val) / (max_val - min_val)
        else:
            df[f'{factor}_normalized'] = 1
    
    # Calculate performance score (inverse of pace - faster is better)
    df['performance_score'] = 1 / (df['elapsed_time'] / df['distance'])
    if df['performance_score'].max() != df['performance_score'].min():
        df['performance_score_normalized'] = (df['performance_score'] - df['performance_score'].min()) / \
                                           (df['performance_score'].max() - df['performance_score'].min())
    else:
        df['performance_score_normalized'] = 1
    
    return df

def create_environmental_performance_chart(env_impact):
    """Create an intuitive environmental performance visualization."""
    
    # Format the pace for hover display
    env_impact['pace_display'] = env_impact['pace_min_km'].apply(
        lambda x: f"{int(x)}:{int((x % 1) * 60):02d}"
    )
    
    fig = px.scatter(
        env_impact,
        x='temperature',
        y='pace_min_km',
        size='distance',
        color='humidity',
        color_continuous_scale='RdYlBu_r',
        hover_data={
            'pace_min_km': False,  # Hide the raw pace value
            'pace_display': True,  # Show formatted pace
            'temperature': ':.1f',
            'humidity': ':.1f',
            'distance': ':.2f',
            'city_name': True
        },
        labels={
            'temperature': 'Temperature (°C)',
            'pace_min_km': 'Pace (min/km)',
            'humidity': 'Humidity (%)',
            'distance': 'Distance (km)',
            'pace_display': 'Pace'
        },
        title="Running Performance by Weather Conditions"
    )
    
    # Customize the layout
    fig.update_layout(
        plot_bgcolor='gray',
        paper_bgcolor='gray',
        font={'color': 'black'},
        height=500,
        showlegend=True,
        hovermode='closest',
        coloraxis_colorbar=dict(
            title="Humidity (%)",
            titleside="right",
            ticks="outside",
            tickfont=dict(size=12, color='black'),
            titlefont=dict(size=14, color='black'),
            len=0.75,          # Length of the colorbar
            thickness=20,      # Width of the colorbar
            x=1.02,           # Position slightly away from the plot
            y=0.5,            # Center vertically
            outlinewidth=1,
            outlinecolor='black',
            bgcolor='white',
        )
    )
    
    # Add gridlines
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(
        showgrid=True, 
        gridwidth=1, 
        gridcolor='LightGray',
        autorange="reversed"  # Faster paces at the top
    )
    
    # Add annotation explaining bubble size
    fig.add_annotation(
        text="Bubble size represents run distance",
        xref="paper", yref="paper",
        x=1, y=-0.15,
        showarrow=False,
        font=dict(size=10, color='black')
    )
    
    return fig

def add_environmental_insights(env_impact):
    """Add clear insights about environmental patterns."""
    st.markdown("#### 🎯 Optimal Running Conditions")
    
    # Find best performing runs (top 10%)
    best_runs = env_impact.nsmallest(int(len(env_impact) * 0.1), 'pace_min_km')
    
    # Calculate optimal ranges
    optimal_conditions = {
        'temperature': {
            'min': best_runs['temperature'].min(),
            'max': best_runs['temperature'].max(),
            'mean': best_runs['temperature'].mean()
        },
        'humidity': {
            'min': best_runs['humidity'].min(),
            'max': best_runs['humidity'].max(),
            'mean': best_runs['humidity'].mean()
        }
    }
    
    cols = st.columns(2)
    with cols[0]:
        st.metric(
            "Optimal Temperature Range",
            f"{optimal_conditions['temperature']['mean']:.1f}°C",
            f"Range: {optimal_conditions['temperature']['min']:.1f}°C to {optimal_conditions['temperature']['max']:.1f}°C"
        )
    
    with cols[1]:
        st.metric(
            "Optimal Humidity Range",
            f"{optimal_conditions['humidity']['mean']:.1f}%",
            f"Range: {optimal_conditions['humidity']['min']:.1f}% to {optimal_conditions['humidity']['max']:.1f}%"
        )
    
    # Add performance insights
    st.markdown("#### 💡 Key Insights")
    
    # Calculate correlations
    temp_corr = env_impact['temperature'].corr(env_impact['pace_min_km'])
    humid_corr = env_impact['humidity'].corr(env_impact['pace_min_km'])
    
    insights = [
        f"- Your fastest runs occur in temperatures between {optimal_conditions['temperature']['min']:.1f}°C and {optimal_conditions['temperature']['max']:.1f}°C",
        f"- Optimal humidity levels are between {optimal_conditions['humidity']['min']:.1f}% and {optimal_conditions['humidity']['max']:.1f}%",
        f"- Temperature has a {'positive' if temp_corr > 0 else 'negative'} correlation ({abs(temp_corr):.2f}) with your pace",
        f"- Humidity has a {'positive' if humid_corr > 0 else 'negative'} correlation ({abs(humid_corr):.2f}) with your pace"
    ]
    
    st.markdown('\n'.join(insights))

def calculate_time_of_day_metrics(strava_df):
    """Calculate performance metrics by time of day."""
    df = strava_df.copy()
    
    # Convert Unix timestamp to datetime
    df['datetime'] = pd.to_datetime(df['start_date_ist'], unit='s')
    df['hour'] = df['datetime'].dt.hour
    
    # Define time slots
    def get_time_slot(hour):
        if 5 <= hour < 8:
            return 'Early Morning (5-8 AM)'
        elif 8 <= hour < 11:
            return 'Morning (8-11 AM)'
        elif 11 <= hour < 16:
            return 'Afternoon (11 AM-4 PM)'
        elif 16 <= hour < 19:
            return 'Evening (4-7 PM)'
        else:
            return 'Night (7 PM-5 AM)'
    
    df['time_slot'] = df['hour'].apply(get_time_slot)
    
    # Calculate metrics by time slot
    time_metrics = df.groupby('time_slot').agg({
        'average_speed': 'mean',
        'average_heartrate': 'mean',
        'temperature': 'mean',
        'pollution_aqi': 'mean',
        'distance': 'mean',
        'id': 'count'  # Number of runs in each slot
    }).reset_index()
    
    # Calculate average pace (minutes per km)
    time_metrics['average_pace'] = 1000 / (time_metrics['average_speed'] * 60)
    
    # Sort time slots in chronological order
    time_slot_order = [
        'Early Morning (5-8 AM)',
        'Morning (8-11 AM)',
        'Afternoon (11 AM-4 PM)',
        'Evening (4-7 PM)',
        'Night (7 PM-5 AM)'
    ]
    time_metrics['time_slot'] = pd.Categorical(
        time_metrics['time_slot'], 
        categories=time_slot_order, 
        ordered=True
    )
    time_metrics = time_metrics.sort_values('time_slot')
    
    # Add summary statistics
    time_metrics['runs_percentage'] = (time_metrics['id'] / time_metrics['id'].sum() * 100).round(1)
    
    return time_metrics, df

def create_location_radar_chart(location_metrics):
    """Create a single radar chart with all cities overlaid."""
    fig = go.Figure()
    
    metrics = [
        'distance_normalized',
        'average_heartrate_normalized', 
        'temperature_normalized',
        'total_elevation_gain_normalized',
        'average_pace_normalized'
    ]
    
    labels = [
        'Distance',
        'Heart Rate',
        'Temperature',
        'Elevation',
        'Pace'
    ]

    colors = px.colors.qualitative.Set3[:len(location_metrics['city_name'].unique())]

    for idx, city in enumerate(location_metrics['city_name'].unique()):
        city_data = location_metrics[location_metrics['city_name'] == city]
        values = [city_data[metric].iloc[0] for metric in metrics]
        values.append(values[0])  # Close the radar chart
        labels_plot = labels + [labels[0]]
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=labels_plot,
            name=city,
            fill='none',
            fillcolor=colors[idx % len(colors)],
            line=dict(color=colors[idx % len(colors)])
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],  # Adjusted to match normalized values
                tickvals=[0, 0.25, 0.5, 0.75, 1],
            ),
            angularaxis=dict(
                rotation=90,
                direction="clockwise"
            )
        ),
        showlegend=True,
        legend=dict(
            orientation="h",  # Horizontal orientation
            yanchor="bottom",  # Anchor to the bottom
            y=1.1,  # Position above the chart
            xanchor="center",  # Center the legend
            x=0.5  # Center the legend horizontally
        ),
        height=700,
        width=700,
        font=dict(color='red')

    )
    
    return fig

def create_yoy_comparison_chart(location_metrics):
    """Create year-over-year comparison radar charts."""
    # Add year column based on start_date_ist
    location_metrics['year'] = pd.to_datetime(location_metrics['start_date_ist'], unit='s').dt.year
    
    # Get available years
    years_available = sorted(location_metrics['year'].unique())
    print(f"Available years: {years_available}")  # Debug print
    
    if len(years_available) < 2:
        return None
    
    # Define metrics and labels
    metrics = [
        'distance_normalized',
        'average_heartrate_normalized', 
        'total_elevation_gain_normalized',
        'average_pace_normalized',
        'temperature_normalized'
    ]
    
    labels = [
        'Distance',
        'Heart Rate',
        'Elevation',
        'Pace',
        'Temperature'
    ]

    fig = go.Figure()
    
    # Print available columns for debugging
    print(f"Available columns: {location_metrics.columns}")
    
    # Calculate yearly averages differently
    for year in years_available:
        year_data = location_metrics[location_metrics['year'] == year]
        
        # Print metrics for debugging
        print(f"\nMetrics for {year}:")
        for metric in metrics:
            if metric in year_data.columns:
                print(f"{metric}: {year_data[metric].mean()}")
        
        values = []
        for metric in metrics:
            if metric in year_data.columns:
                avg_value = year_data[metric].mean()
                values.append(avg_value)
            else:
                print(f"Missing metric: {metric}")
        
        if values:  # Only add trace if we have values
            values = [year_data[metric].mean() * 100 for metric in metrics]
            values.append(values[0])  # Close the polygon
            labels_plot = labels + [labels[0]]
            
            color = '#FF9999' if year == years_available[0] else '#66B2FF'
            
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=labels_plot,
                name=str(int(year)),
                fill='none',
                fillcolor=color,
                line=dict(color=color)
            ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[20, 40, 60, 80, 100],
            ),
            angularaxis=dict(
                rotation=90,
                direction="clockwise"
            )
        ),
        legend=dict(
            orientation="h",  # Horizontal orientation
            yanchor="bottom",  # Anchor to the bottom
            y=1.1,  # Position above the chart
            xanchor="center",  # Center the legend
            x=0.5  # Center the legend horizontally
        ),
        height=700,
        width=700,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='red'),  # Change text color to black
    )
    
    return fig

def add_combined_metrics_tab(tab, strava_df):
    """Add combined metrics visualizations with improved UI."""
    with tab:
        st.header("Environmental Impact on Running Performance")
        # Create three main sections using tabs for better organization
        section_tabs = st.tabs(["Environmental Impact", "Location Analysis", "Time of Day Patterns"])
        
        with section_tabs[0]:
            st.header("🌡️ Environmental Impact")
            
            env_impact = calculate_environmental_impact(strava_df)
            
            if not env_impact.empty:
                # Optimal conditions summary
                st.subheader("Optimal Running Conditions")
                metrics_cols = st.columns(4)
                
                # Get optimal conditions (from best performing runs - top 10%)
                best_runs = env_impact.nsmallest(int(len(env_impact) * 0.1), 'pace_min_km')
                
                with metrics_cols[0]:
                    optimal_temp = best_runs['temperature'].mean()
                    temp_range = f"±{(best_runs['temperature'].max() - best_runs['temperature'].min())/2:.1f}°C"
                    st.metric("Best Temperature", f"{optimal_temp:.1f}°C", temp_range)
                
                with metrics_cols[1]:
                    optimal_humidity = best_runs['humidity'].mean()
                    humidity_range = f"±{(best_runs['humidity'].max() - best_runs['humidity'].min())/2:.1f}%"
                    st.metric("Best Humidity", f"{optimal_humidity:.1f}%", humidity_range)
                
                with metrics_cols[2]:
                    optimal_aqi = best_runs['pollution_aqi'].mean()
                    aqi_range = f"±{(best_runs['pollution_aqi'].max() - best_runs['pollution_aqi'].min())/2:.1f}"
                    st.metric("Best AQI", f"{optimal_aqi:.1f}", aqi_range)
                
                with metrics_cols[3]:
                    optimal_pm25 = best_runs['pollution_pm25'].mean()
                    pm25_range = f"±{(best_runs['pollution_pm25'].max() - best_runs['pollution_pm25'].min())/2:.1f}"
                    st.metric("Best PM2.5", f"{optimal_pm25:.1f}", pm25_range)
                
                # Main performance visualization
                st.subheader("Performance vs Weather Conditions")
                fig = create_environmental_performance_chart(env_impact)
                st.plotly_chart(fig, use_container_width=True)
                
                # Insights section
                st.subheader("💡 Key Insights")
                
                # Calculate correlations
                correlations = {
                    'Temperature': env_impact['temperature'].corr(env_impact['pace_min_km']),
                    'Humidity': env_impact['humidity'].corr(env_impact['pace_min_km']),
                    'AQI': env_impact['pollution_aqi'].corr(env_impact['pace_min_km']),
                    'PM2.5': env_impact['pollution_pm25'].corr(env_impact['pace_min_km'])
                }
                
                # Create correlation summary
                insight_cols = st.columns(2)
                with insight_cols[0]:
                    st.markdown("**Impact on Performance:**")
                    for factor, corr in correlations.items():
                        impact = "slows you down" if corr > 0 else "helps your performance"
                        strength = abs(corr)
                        if strength < 0.2:
                            impact_str = "minimal impact"
                        elif strength < 0.4:
                            impact_str = "moderate impact"
                        else:
                            impact_str = "strong impact"
                        st.markdown(f"- {factor}: {impact_str} ({impact})")
                
                with insight_cols[1]:
                    st.markdown("**Recommendations:**")
                    st.markdown(f"- Plan longer runs when temperature is near {optimal_temp:.1f}°C")
                    st.markdown(f"- Optimal humidity is around {optimal_humidity:.1f}%")
                    st.markdown(f"- Consider indoor runs when AQI > {optimal_aqi + 20:.1f}")
                    
                # Distribution Analysis
                st.subheader("Condition Distributions")
                dist_cols = st.columns(2)
                
                with dist_cols[0]:
                    temp_fig = px.histogram(env_impact, x='temperature', 
                                          title="Temperature Distribution of Runs",
                                          labels={'temperature': 'Temperature (°C)'})
                    st.plotly_chart(temp_fig, use_container_width=True)
                
                with dist_cols[1]:
                    humidity_fig = px.histogram(env_impact, x='humidity',
                                              title="Humidity Distribution of Runs",
                                              labels={'humidity': 'Humidity (%)'})
                    st.plotly_chart(humidity_fig, use_container_width=True)
            
            else:
                st.warning("Not enough environmental data to analyze performance patterns.")
        
        with section_tabs[1]:
            location_col, env_col = st.columns(2)
        # 1. Location Performance Profile
            with location_col:
                st.subheader("🌍 Location Analysis")
                location_metrics = calculate_location_metrics(strava_df)
                
                if not location_metrics.empty:
                    # Summary metrics first
                    best_pace_city = location_metrics.loc[location_metrics['average_pace'].idxmin(), 'city_name']
                    most_runs_city = location_metrics.loc[location_metrics['id'].idxmax(), 'city_name']
                    
                    # Create two info boxes
                    st.info(f"📍 Most frequent running location: **{most_runs_city}** " 
                        f"({int(location_metrics.loc[location_metrics['id'].idxmax(), 'id'])} runs)")
                    st.success(f"🏃 Best performance location: **{best_pace_city}**")
                    
                    # Show detailed city comparison
                    st.markdown("##### City Performance Comparison")
                    
                    # Create a clean comparison table
                    comparison_df = location_metrics[['city_name', 'average_pace', 'average_heartrate', 
                                                'temperature', 'pollution_aqi', 'id']].copy()
                    comparison_df['average_pace'] = comparison_df['average_pace'].apply(
                        lambda x: f"{int(x)}:{int((x % 1) * 60):02d} /km")
                    comparison_df.columns = ['City', 'Avg Pace', 'Avg HR', 'Temp (°C)', 'AQI', 'Total Runs']
                    st.dataframe(comparison_df.set_index('City'), use_container_width=True)
                    
            # Radar chart for all locations
            # top_locations = location_metrics.nlargest(5, 'id')
            col1, col2 = st.columns(2)
            # fig = create_location_radar_chart(location_metrics)
            # st.plotly_chart(fig, use_container_width=True)

            with col1:
                st.subheader("All Locations Comparison")
                # print("Location Metrics DataFrame:")
                # print(location_metrics)  # Debug log to check the DataFrame contents

                fig = create_location_radar_chart(location_metrics)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("Year-over-Year Analysis")
                yoy_chart = create_yoy_comparison_chart(location_metrics)
                if yoy_chart:
                    st.plotly_chart(yoy_chart, use_container_width=True)
                else:
                    st.info("Year-over-year comparison will be available once data from multiple years is collected.")
            
            # 2. Environmental Impact Analysis
            with env_col:
                st.subheader("🌡️ Environmental Impact")
                env_impact = calculate_environmental_impact(strava_df)
                
                if not env_impact.empty:
                    # Show optimal conditions
                    optimal_perf = env_impact.loc[env_impact['performance_score_normalized'].idxmax()]
                    
                    st.markdown("##### Optimal Running Conditions")
                    metrics_cols = st.columns(2)
                    with metrics_cols[0]:
                        st.metric("Best Temperature", f"{optimal_perf['temperature']:.1f}°C")
                        st.metric("Best Humidity", f"{optimal_perf['humidity']:.1f}%")
                    with metrics_cols[1]:
                        st.metric("Best AQI", f"{optimal_perf['pollution_aqi']:.1f}")
                        st.metric("Best PM2.5", f"{optimal_perf['pollution_pm25']:.1f}")
                    
                    # Interactive performance chart
                    st.markdown("##### Performance vs Conditions")
                    fig = px.scatter(
                        env_impact,
                        x='temperature',
                        y='performance_score_normalized',
                        size='distance',
                        color='humidity',
                        hover_data=['city_name', 'pollution_aqi'],
                        title="Running Performance by Temperature and Humidity",
                        labels={
                            'temperature': 'Temperature (°C)',
                            'performance_score_normalized': 'Performance Score',
                            'humidity': 'Humidity (%)'
                        }
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
        
        with section_tabs[2]:
        # 3. Time of Day Analysis (Full Width)
            st.subheader("⏰ Time of Day Analysis")
            time_metrics, time_df = calculate_time_of_day_metrics(strava_df)
            
            if not time_metrics.empty:
                # Show summary insights
                best_time = time_metrics.loc[time_metrics['average_pace'].idxmin(), 'time_slot']
                most_consistent_time = time_metrics.loc[time_metrics['id'].idxmax(), 'time_slot']
                
                time_cols = st.columns(2)
                with time_cols[0]:
                    st.info(f"⭐ Best performance time: **{best_time}**")
                with time_cols[1]:
                    st.info(f"📊 Most consistent time: **{most_consistent_time}** " 
                        f"({int(time_metrics.loc[time_metrics['id'].idxmax(), 'id'])} runs)")
                
                # Time performance visualization
                fig = px.bar(
                    time_metrics,
                    x='time_slot',
                    y=['average_pace', 'average_heartrate'],
                    title="Performance Metrics by Time of Day",
                    barmode='group',
                    labels={
                        'time_slot': 'Time of Day',
                        'average_pace': 'Avg Pace (min/km)',
                        'average_heartrate': 'Avg Heart Rate'
                    }
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # Additional metrics table
                st.markdown("##### Detailed Time Metrics")
                detailed_time = time_metrics.copy()
                detailed_time['average_pace'] = detailed_time['average_pace'].apply(
                    lambda x: f"{int(x)}:{int((x % 1) * 60):02d} /km")
                detailed_time['runs_percentage'] = detailed_time['runs_percentage'].apply(
                    lambda x: f"{x}%")
                detailed_time = detailed_time[['time_slot', 'average_pace', 'average_heartrate', 
                                            'temperature', 'id', 'runs_percentage']]
                detailed_time.columns = ['Time Slot', 'Avg Pace', 'Avg HR', 'Avg Temp (°C)', 
                                    'Total Runs', 'Distribution']
                st.dataframe(detailed_time.set_index('Time Slot'), use_container_width=True)

def calculate_date_for_range(range_option):
    """Calculate the start date for a given range option, returning datetime at start of day."""
    today = datetime.now().date()
    
    if range_option == "Today":
        target_date = today
    elif range_option == "Yesterday":
        target_date = today - timedelta(days=1)
    elif range_option == "Last 7 Days":
        target_date = today - timedelta(days=7)
    elif range_option == "Last 14 Days":
        target_date = today - timedelta(days=14)
    elif range_option == "Last 30 Days":
        target_date = today - timedelta(days=30)
    elif range_option == "Last 90 Days":
        target_date = today - timedelta(days=90)
    elif range_option == "Last 180 Days":
        target_date = today - timedelta(days=180)
    elif range_option == "This Year":
        target_date = datetime(today.year, 1, 1).date()
    elif range_option == "Last Year":
        target_date = datetime(today.year - 1, 1, 1).date()
    else:
        return None
    
    # Convert date to datetime at start of day
    return datetime.combine(target_date, datetime.min.time())

def sync_data(time_range):
    """Syncs data from Strava API for the selected time range."""
    try:
        # Initialize Strava client
        client = authenticate_strava()
        if not client:
            return False, "Failed to authenticate with Strava"
        
        # Get datetime for start of selected range
        after_datetime = calculate_date_for_range(time_range)
        if after_datetime:
            # Add timezone info to match Strava's timezone-aware datetimes
            after_datetime = after_datetime.replace(tzinfo=timezone.utc)
        
        # Stream and process activities
        activities_processed = 0
        conn = sqlite3.connect("ai_running_coach.db")
        
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
        
        # Format message with date range
        start_date = after_datetime.strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        return True, f"Successfully synced {activities_processed} new activities from {start_date} to {end_date}"
        
    except Exception as e:
        return False, f"Error during sync: {str(e)}"

def create_activity_trends_tab(tab, strava_df):
    """Create detailed activity trend visualizations."""
    with tab:
        st.header("Activity Trends")
        
        # Allow user to select metric and time period
        col1, col2 = st.columns(2)
        with col1:
            metric = st.selectbox(
                "Select Metric",
                ["Distance", "Average Pace", "Average Heart Rate", "Total Elevation Gain"]
            )
        
        with col2:
            period = st.selectbox(
                "Select Time Period",
                ["Last 30 Days", "Last 90 Days", "Last 180 Days", "Last Year", "This year", "Overall"]
            )
            
        # Create trend visualization
        trend_data = get_trend_data(strava_df, metric, period)
        if not trend_data.empty:
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=trend_data.index,
                y=trend_data.iloc[:, 0],
                mode='lines+markers',
                name=metric,
                line=dict(color='rgb(102,178,255)', width=2),
                marker=dict(size=6)
            ))
            
            # Add rolling average
            rolling_avg = trend_data.iloc[:, 0].rolling(window=7).mean()
            fig.add_trace(go.Scatter(
                x=trend_data.index,
                y=rolling_avg,
                mode='lines',
                name='7-day moving average',
                line=dict(color='rgb(255,153,153)', width=2, dash='dash')
            ))
            
            fig.update_layout(
                title=f"{metric} Over Time",
                xaxis=dict(
                    title="Date",
                    tickformat="%b %Y",
                    tickangle=45,
                    gridcolor='rgba(128,128,128,0.2)',
                    showgrid=True,
                ),
                yaxis=dict(
                    title=metric,
                    gridcolor='rgba(128,128,128,0.2)',
                    showgrid=True,
                ),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                height=500,
                showlegend=True,
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add summary statistics
            st.subheader("Summary Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Average",
                    f"{trend_data.iloc[:, 0].mean():.2f}",
                    delta=None
                )
            
            with col2:
                st.metric(
                    "Median",
                    f"{trend_data.iloc[:, 0].median():.2f}",
                    delta=None
                )
            
            with col3:
                st.metric(
                    "Standard Deviation",
                    f"{trend_data.iloc[:, 0].std():.2f}",
                    delta=None
                )
        else:
            st.warning("No data available for the selected period")

# --- Streamlit Layout and Display ---
def main():
    st.set_page_config(layout="wide")
    st.title("AI Running Coach Metrics")

    # Sidebar with title and sync button
    
    with st.sidebar:
        st.title("Strava Integration")
        
        # Time range selection with date-based descriptions
        time_ranges = [
            "Today",
            "Yesterday",
            "Last 7 Days",
            "Last 14 Days",
            "Last 30 Days",
            "Last 90 Days",
            "Last 180 Days",
            "This Year",
            "Last Year"
        ]
        
        selected_range = st.selectbox(
            "Select date range to sync",
            time_ranges,
            index=2  # Default to "Last 7 Days"
        )
        
        # Add sync button with date-based messaging
        if st.button("🔄 Sync Data"):
            start_date = calculate_date_for_range(selected_range)
            with st.spinner(f"Syncing activities from {start_date.strftime('%Y-%m-%d')} to today..."):
                success, message = sync_data(selected_range)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            
        # Display last sync time as date
        conn = sqlite3.connect("ai_running_coach.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(start_date_ist) FROM strava_activities_weather")
        last_sync = cursor.fetchone()[0]
        conn.close()
        
        if last_sync:
            last_sync_date = datetime.fromtimestamp(last_sync).date()
            st.write(f"Last synced date: {last_sync_date.strftime('%Y-%m-%d')}")

    strava_df, splits_df, best_efforts_df = prepare_data()
    comparison_periods = ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Year-to-Date", "Last Year", "Overall"]
    tabs = st.tabs(["Performance Metrics", "Physiological Metrics", "Elevation & Cadence Metrics", "Environmental Metrics", "Inferred Metrics", "Deeper Insights", "Activity Trends"])

    with tabs[0]: # Performance Metrics
        st.header("Performance Metrics")
        metrics = ["Distance", "Average Pace"]
        for metric in metrics:
            st.subheader(metric)
            cols = st.columns(len(comparison_periods), gap="medium")
            for i, period in enumerate(comparison_periods):
                with cols[i]:
                    current_value, _, median_value, _, _ = calculate_metric(strava_df, metric, period)
                    previous_period = get_previous_period(period)
                    previous_value, _, previous_median_value, _, _ = calculate_metric(strava_df, metric, previous_period) if previous_period else (None, None, None, None, None)
                    percentage_change = calculate_percentage_change(current_value, previous_value)
                    
                    if metric == "Average Pace" and current_value is not None:
                        current_value = f"{int(current_value // 1)}:{int((current_value % 1) * 60):02d}"
                        if previous_value is not None:
                            previous_value = f"{int(previous_value // 1)}:{int((previous_value % 1) * 60):02d}"
                    
                    if current_value is not None:
                        st.metric(label=period, value=current_value, delta=f"{percentage_change:.2f}%" if percentage_change is not None else None)
                        st.caption(f"Avg: {current_value}, Median: {median_value:.2f}" if median_value is not None else f"Avg: {current_value}, Median: N/A")
                    else:
                        st.metric(label=period, value="N/A")
                        st.caption("Avg: N/A, Median: N/A")
                    
                    trend_data = get_trend_data(strava_df, metric, period)
                    if not trend_data.empty:
                        st.line_chart(trend_data, height=200)

    with tabs[1]: # Physiological Metrics
        st.header("Physiological Metrics")
        metrics = ["Average Heart Rate", "Calories Burned", "Suffer Score"]
        for metric in metrics:
            st.subheader(metric)
            cols = st.columns(len(comparison_periods), gap="medium")
            for i, period in enumerate(comparison_periods):
                with cols[i]:
                    current_value, _, median_value, _, _ = calculate_metric(strava_df, metric, period)
                    previous_period = get_previous_period(period)
                    previous_value, _, previous_median_value, _, _ = calculate_metric(strava_df, metric, previous_period) if previous_period else (None, None, None, None, None)
                    percentage_change = calculate_percentage_change(current_value, previous_value)
                    
                    if current_value is not None:
                        st.metric(label=period, value=f"{current_value:.2f}", delta=f"{percentage_change:.2f}%" if percentage_change is not None else None)
                        st.caption(f"Avg: {current_value:.2f}, Median: {median_value:.2f}" if median_value is not None else f"Avg: {current_value:.2f}, Median: N/A")
                    else:
                        st.metric(label=period, value="N/A")
                        st.caption("Avg: N/A, Median: N/A")
                    
                    trend_data = get_trend_data(strava_df, metric, period)
                    if not trend_data.empty:
                        st.line_chart(trend_data, height=200)

    with tabs[2]: # Elevation & Cadence Metrics
        st.header("Elevation & Cadence Metrics")
        metrics = ["Total Elevation Gain", "Average Cadence"]
        for metric in metrics:
            st.subheader(metric)
            cols = st.columns(len(comparison_periods), gap="medium")
            for i, period in enumerate(comparison_periods):
                with cols[i]:
                    current_value, _, median_value, _, _ = calculate_metric(strava_df, metric, period)
                    previous_period = get_previous_period(period)
                    previous_value, _, previous_median_value, _, _ = calculate_metric(strava_df, metric, previous_period) if previous_period else (None, None, None, None, None)
                    percentage_change = calculate_percentage_change(current_value, previous_value)
                    
                    if current_value is not None:
                        st.metric(label=period, value=f"{current_value:.2f}", delta=f"{percentage_change:.2f}%" if percentage_change is not None else None)
                        st.caption(f"Avg: {current_value:.2f}, Median: {median_value:.2f}" if median_value is not None else f"Avg: {current_value:.2f}, Median: N/A")
                    else:
                        st.metric(label=period, value="N/A")
                        st.caption("Avg: N/A, Median: N/A")
                    
                    trend_data = get_trend_data(strava_df, metric, period)
                    if not trend_data.empty:
                        st.line_chart(trend_data, height=200)

    with tabs[3]: # Environmental Metrics
        st.header("Environmental Metrics")
        metrics = ["Temperature", "Feels Like Temperature", "Humidity", "Pollution PM2.5", "Pollution AQI"]
        for metric in metrics:
            st.subheader(metric)
            cols = st.columns(len(comparison_periods), gap="medium")
            for i, period in enumerate(comparison_periods):
                with cols[i]:
                    current_value, _, median_value, _, _ = calculate_metric(strava_df, metric, period)
                    previous_period = get_previous_period(period)
                    previous_value, _, previous_median_value, _, _ = calculate_metric(strava_df, metric, previous_period) if previous_period else (None, None, None, None, None)
                    percentage_change = calculate_percentage_change(current_value, previous_value)
                    
                    if current_value is not None:
                        st.metric(label=period, value=f"{current_value:.2f}", delta=f"{percentage_change:.2f}%" if percentage_change is not None else None)
                        st.caption(f"Avg: {current_value:.2f}, Median: {median_value:.2f}" if median_value is not None else f"Avg: {current_value:.2f}, Median: N/A")
                    else:
                        st.metric(label=period, value="N/A")
                        st.caption("Avg: N/A, Median: N/A")
                    
                    trend_data = get_trend_data(strava_df, metric, period)
                    if not trend_data.empty:
                        st.line_chart(trend_data, height=200)
    
    with tabs[4]:  # Inferred Metrics
        st.header("Inferred Metrics")
        
        # Calculate all weekly metrics at once
        weekly_pace_var, weekly_hr_zones, weekly_runs, weekly_gap = calculate_weekly_metrics(strava_df, splits_df)
        
        # 1. Pace Variation Trend
        st.subheader("Weekly Pace Variation Trend")
        if not weekly_pace_var.empty:
            st.line_chart(weekly_pace_var.set_index('week')['variation'])
            st.caption("Lower values indicate more consistent pacing within runs")
        else:
            st.write("No pace variation data available")
        
        # 2. Heart Rate Zones Distribution Trend
        st.subheader("Weekly Heart Rate Zone Distribution")
        if not weekly_hr_zones.empty:
            st.area_chart(weekly_hr_zones)
            st.caption("Shows percentage of runs in each heart rate zone per week")
        else:
            st.write("No heart rate zone data available")
        
        # 3. Running Consistency Trend
        st.subheader("Weekly Running Consistency")
        if not weekly_runs.empty:
            fig_consistency = {
                'data': [{
                    'x': weekly_runs['week'],
                    'y': weekly_runs['num_runs'],
                    'type': 'bar',
                    'name': 'Runs per Week'
                }],
                'layout': {
                    'title': 'Number of Runs per Week',
                    'xaxis': {'title': 'Week'},
                    'yaxis': {'title': 'Number of Runs'}
                }
            }
            st.plotly_chart(fig_consistency)
        else:
            st.write("No running consistency data available")
        
        # 4. Grade Adjusted Pace Trend
        st.subheader("Weekly Grade Adjusted Pace Trend")
        if not weekly_gap.empty:
            # Convert seconds to minutes for display
            weekly_gap['pace_minutes'] = weekly_gap['average_grade_adjusted_speed'] / 60
            st.line_chart(weekly_gap.set_index('week')['pace_minutes'])
            st.caption("Lower values indicate faster pace (minutes per km), adjusted for elevation changes")
        else:
            st.write("No grade adjusted pace data available")

    with tabs[5]:  # Combined Metrics
        add_combined_metrics_tab(tabs[5], strava_df)

    with tabs[6]:  # Trends
        create_activity_trends_tab(tabs[6], strava_df)

if __name__ == "__main__":
    main()