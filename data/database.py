import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name="running_coach.db"):
        self.db_name = db_name
        self.create_database()

    def create_database(self):
        """Create all necessary tables in one SQLite database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Core Activities Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            start_date INTEGER,
            start_date_local TEXT,
            distance REAL,
            elapsed_time INTEGER,
            moving_time INTEGER,
            average_speed REAL,
            max_speed REAL,
            average_heartrate REAL,
            max_heartrate REAL,
            calories INTEGER,
            total_elevation_gain REAL,
            average_cadence REAL,
            type TEXT,
            start_latitude REAL,
            start_longitude REAL,
            timezone TEXT,
            gear_id TEXT,
            device_name TEXT,
            map_summary_polyline TEXT,
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
            city_name TEXT
        )
        """)

        # Splits Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER,
            split_number INTEGER,
            distance REAL,
            elapsed_time INTEGER,
            average_speed REAL,
            elevation_difference REAL,
            moving_time INTEGER,
            average_heartrate REAL,
            average_grade_adjusted_speed REAL,
            FOREIGN KEY(activity_id) REFERENCES activities(id)
        )
        """)

        # Initial Goals & Plans Tables (for future use)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER,
            target_date INTEGER,
            goal_type TEXT,
            target_value REAL,
            status TEXT,
            notes TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            target_date INTEGER,
            target_value REAL,
            status TEXT,
            FOREIGN KEY(goal_id) REFERENCES goals(id)
        )
        """)

        conn.commit()
        conn.close()

    def store_activity(self, activity_data, splits_data):
        """Store activity and its splits data"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # Store main activity
            placeholders = ', '.join(':' + key for key in activity_data.keys())
            columns = ', '.join(activity_data.keys())
            
            cursor.execute(f"""
                INSERT OR REPLACE INTO activities ({columns})
                VALUES ({placeholders})
            """, activity_data)

            # Store splits
            if splits_data:
                for split in splits_data:
                    split_placeholders = ', '.join(':' + key for key in split.keys())
                    split_columns = ', '.join(split.keys())
                    
                    cursor.execute(f"""
                        INSERT OR REPLACE INTO splits ({split_columns})
                        VALUES ({split_placeholders})
                    """, split)

            conn.commit()
            return True
        except Exception as e:
            print(f"Error storing activity: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def activity_exists(self, activity_id):
        """Check if an activity already exists"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM activities WHERE id = ?", (activity_id,))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def get_latest_activity_date(self):
        """Get the most recent activity date"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(start_date) FROM activities")
        result = cursor.fetchone()[0]
        conn.close()
        return datetime.fromtimestamp(result) if result else None