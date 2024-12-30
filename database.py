import sqlite3, time


DATABASE_NAME = "ai_running_coach.db"

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
    
    # Create splits_data table
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER,
            name TEXT,
            distance REAL,
            elapsed_time REAL,
            start_date TEXT,
            FOREIGN KEY (activity_id) REFERENCES strava_activities_weather(id)
        )
    """)

    conn.commit()
    conn.close()

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
    
    # Insert into splits_data table
    if activity.splits_metric:
        print(f"[DB] Processing splits for activity {activity.id}")
        for split in activity.splits_metric:
            splits_data = (
                activity.id,
                split.split,
                split.distance,
                split.elapsed_time,
                split.average_speed,
                split.elevation_difference,
                split.moving_time,
                split.average_heartrate,
                split.average_grade_adjusted_speed
            )
            cursor.execute("""
                INSERT INTO splits_data (activity_id, split, distance, elapsed_time, average_speed, elevation_difference, moving_time, average_heartrate, average_grade_adjusted_speed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, splits_data)
            conn.commit()
    
    # Insert into best_efforts_data table
    if activity.best_efforts:
        print(f"[DB] Processing best efforts for activity {activity.id}")
        for effort in activity.best_efforts:
            best_efforts_data = (
                activity.id,
                effort.name,
                effort.distance,
                effort.elapsed_time,
                effort.start_date.isoformat() if effort.start_date else None
            )
            cursor.execute("""
                INSERT INTO best_efforts_data (activity_id, name, distance, elapsed_time, start_date) VALUES (?, ?, ?, ?, ?)
            """, best_efforts_data)
            conn.commit()
    print(f"[DB] Completed processing activity {activity.id}")

def fetch_data_from_db(query):
    """Fetches data from the database using the provided query."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    return data

def activity_exists(conn, activity_id):
    """Check if an activity already exists in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM strava_activities_weather WHERE id = ?", (activity_id,))
    return cursor.fetchone() is not None