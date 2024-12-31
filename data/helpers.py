from datetime import datetime, timezone, timedelta

def calculate_date_range(range_option):
    """Calculate start and end dates based on range selection"""
    today = datetime.now()
    
    if range_option == "Last 7 Days":
        start_date = today - timedelta(days=7)
    elif range_option == "Last 14 Days":
        start_date = today - timedelta(days=14)
    elif range_option == "Last 30 Days":
        start_date = today - timedelta(days=30)
    elif range_option == "Last 90 Days":
        start_date = today - timedelta(days=90)
    else:
        start_date = datetime(today.year, 1, 1)
    
    return start_date.replace(tzinfo=timezone.utc)

def process_activity_data(activity_dict):
    """Process raw activity and weather data into database format"""
    activity = activity_dict['strava_data']
    weather = activity_dict['weather_data']
    pollution = activity_dict['pollution_data']
    
    # Get pollution data (average if multiple readings)
    pollution_data = {
        'aqi': None,
        'pm2_5': None,
        'co': None,
        'no': None,
        'no2': None,
        'o3': None,
        'so2': None,
        'pm10': None,
        'nh3': None
    }
    
    if pollution and 'list' in pollution and pollution['list']:
        readings = pollution['list']
        pollution_data = {
            'aqi': sum(r['main']['aqi'] for r in readings) / len(readings),
            'pm2_5': sum(r['components']['pm2_5'] for r in readings) / len(readings),
            'co': sum(r['components']['co'] for r in readings) / len(readings),
            'no': sum(r['components']['no'] for r in readings) / len(readings),
            'no2': sum(r['components']['no2'] for r in readings) / len(readings),
            'o3': sum(r['components']['o3'] for r in readings) / len(readings),
            'so2': sum(r['components']['so2'] for r in readings) / len(readings),
            'pm10': sum(r['components']['pm10'] for r in readings) / len(readings),
            'nh3': sum(r['components']['nh3'] for r in readings) / len(readings)
        }

    # Main activity data
    activity_data = {
        'id': activity.id,
        'start_date': int(activity.start_date.timestamp()),
        'start_date_local': activity.start_date_local.isoformat(),
        'distance': float(activity.distance) / 1000,  # Convert to km
        'elapsed_time': activity.elapsed_time.seconds if activity.elapsed_time else None,
        'moving_time': activity.moving_time.seconds if activity.moving_time else None,
        'average_speed': activity.average_speed,
        'max_speed': activity.max_speed,
        'average_heartrate': activity.average_heartrate,
        'max_heartrate': activity.max_heartrate,
        'calories': activity.calories,
        'total_elevation_gain': activity.total_elevation_gain,
        'average_cadence': activity.average_cadence,
        'type': activity.type,
        'start_latitude': activity.start_latlng.lat if activity.start_latlng else None,
        'start_longitude': activity.start_latlng.lon if activity.start_latlng else None,
        'timezone': activity.timezone,
        'gear_id': activity.gear_id,
        'device_name': activity.device_name,
        'map_summary_polyline': activity.map.summary_polyline if activity.map else None,
        'temperature': weather['data'][0]['temp'] if weather and 'data' in weather else None,
        'feels_like': weather['data'][0]['feels_like'] if weather and 'data' in weather else None,
        'humidity': weather['data'][0]['humidity'] if weather and 'data' in weather else None,
        'weather_conditions': weather['data'][0]['weather'][0]['description'] if weather and 'data' in weather and weather['data'][0].get('weather') else None,
        'pollution_aqi': pollution_data['aqi'],
        'pollution_pm25': pollution_data['pm2_5'],
        'pollution_co': pollution_data['co'],
        'pollution_no': pollution_data['no'],
        'pollution_no2': pollution_data['no2'],
        'pollution_o3': pollution_data['o3'],
        'pollution_so2': pollution_data['so2'],
        'pollution_pm10': pollution_data['pm10'],
        'pollution_nh3': pollution_data['nh3'],
        'city_name': None  # Will add reverse geocoding later
    }

    # Process splits data
    splits_data = []
    if activity.splits_metric:
        for split in activity.splits_metric:
            splits_data.append({
                'activity_id': activity.id,
                'split_number': split.split,
                'distance': split.distance,
                'elapsed_time': split.elapsed_time.seconds if split.elapsed_time else None,
                'average_speed': split.average_speed,
                'elevation_difference': split.elevation_difference,
                'moving_time': split.moving_time.seconds if split.moving_time else None,
                'average_heartrate': split.average_heartrate,
                'average_grade_adjusted_speed': split.average_grade_adjusted_speed
            })

    return activity_data, splits_data