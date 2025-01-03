import pandas as pd
from datetime import datetime

def format_last_7_runs_table(runs):
    """Formats the last 7 runs data into a Pandas DataFrame."""
    if not runs:
         return pd.DataFrame()
    
    df = pd.DataFrame(runs)

    # Convert start_date_local to datetime objects, handling None
    df['start_date_local'] = pd.to_datetime(df['start_date_local'], errors='coerce')

    # Format start_date_local to a human-readable string
    df['start_date_local'] = df['start_date_local'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate pace in km/h
    df['pace'] = df.apply(lambda row: row['distance'] / (row['elapsed_time'] / 3600) if row['elapsed_time'] and row['distance'] else None, axis=1)

    # Convert elapsed_time from seconds to minutes for display
    df['elapsed_time'] = df['elapsed_time'].apply(lambda x: f"{int(x // 60)}:{int(x % 60):02d}" if x else None)
    
    # Select and rename the columns to be displayed
    df = df[[
        'start_date_local',
        'distance',
        'elapsed_time',
        'pace',
        'average_heartrate',
        'total_elevation_gain',
        'temperature',
        'weather_conditions',
        'pollution_aqi'
    ]].rename(columns={
        'start_date_local': 'Start Time',
        'distance': 'Distance (km)',
        'elapsed_time': 'Elapsed Time (min)',
        'pace': 'Pace (km/h)',
        'average_heartrate': 'Avg HR (bpm)',
        'total_elevation_gain': 'Elevation (m)',
        'temperature': 'Temp (°C)',
        'weather_conditions': 'Weather',
        'pollution_aqi': 'AQI'
    })
    
    return df

def format_combined_average_metrics_table(avg_metrics_list, periods):
    """Formats the average metrics into a single Pandas DataFrame with rows for each period."""
    if not avg_metrics_list:
        return pd.DataFrame()

    formatted_data = []
    for i, avg_metrics in enumerate(avg_metrics_list):
         if avg_metrics:
            df = pd.DataFrame([avg_metrics])
            
             # Calculate pace in km/h
            df['pace'] = df.apply(lambda row: row['distance'] / (row['elapsed_time'] / 3600) if row['elapsed_time'] and row['distance'] else None, axis=1)
           
            # Format elapsed_time from seconds to minutes for display
            df['elapsed_time'] = df['elapsed_time'].apply(lambda x: f"{int(x // 60)}:{int(x % 60):02d}" if x else None)

            formatted_row = {
                    'Period': periods[i],
                    'Runs': df['num_runs'].iloc[0],
                    'Avg Distance (km)': df['distance'].iloc[0],
                    'Avg Time (min)': df['elapsed_time'].iloc[0],
                    'Avg Pace (km/h)': df['pace'].iloc[0],
                    'Avg HR (bpm)': df['average_heartrate'].iloc[0],
                    'Avg Elevation (m)': df['total_elevation_gain'].iloc[0],
                    'Avg Temp (°C)': df['temperature'].iloc[0],
                    'Avg AQI': df['pollution_aqi'].iloc[0]
                }
            formatted_data.append(formatted_row)

    df = pd.DataFrame(formatted_data)
    df = df.set_index('Period')
    return df