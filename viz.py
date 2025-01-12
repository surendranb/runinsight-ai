import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from data import DATABASE_NAME
import sqlite3
import pytz

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
    df['pace'] = df.apply(lambda row: row['distance'] / (row['moving_time'] / 3600) if row['moving_time'] and row['distance'] else None, axis=1)

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

def create_trend_chart(df, metric, title):
    """Creates a line chart for trend analysis."""
    if df.empty:
        return None

    fig = go.Figure()
    
    if metric == 'pace':
        # Convert pace from km/h to min/km for y-axis labels and tooltip
        df['pace_min_km'] = 60 / df['average_speed'] if 'average_speed' in df.columns else None
        fig.add_trace(go.Scatter(
            x=df['start_date_ist'],
            y=df['pace_min_km'],
            mode='lines+markers',
            name=metric,
            hovertemplate="Pace: %{y:.2f} min/km<br>Date: %{x|%Y-%m-%d}<extra></extra>"
         ))
        y_axis_label = 'Pace (min/km)'
    elif metric == 'distance':
        fig.add_trace(go.Scatter(
            x=df['start_date_ist'],
            y=df['distance'],
            mode='lines+markers',
            name=metric,
            hovertemplate="Distance: %{y:.2f} km<br>Date: %{x|%Y-%m-%d}<extra></extra>"
        ))
        y_axis_label = 'Distance (km)'
    else:
        return None # Return none if metric does not match

    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Date",
         yaxis_title=y_axis_label,
        hovermode='x unified'
    )

    return fig

def format_volume_goal_progress(progress):
    """Formats the volume goal progress data into a Pandas DataFrame."""
    if not progress:
        return pd.DataFrame()

    formatted_data = []
    for key, value in progress.items():
        if key == "total_distance":
            formatted_data.append({
                "Goal": "Total Distance (km)",
                "Target": value.get("goal", "N/A"),
                "Progress": value.get("progress", "N/A")
            })
        elif key.startswith("runs_"):
             distance = key.split("_")[1].replace("km", "")
             formatted_data.append({
                "Goal": f"Number of {distance}km Runs",
                "Target": value.get("goal", "N/A"),
                "Progress": value.get("progress", "N/A")
            })
    
    df = pd.DataFrame(formatted_data)
    return df

def format_performance_goal_progress(progress):
    """Formats the performance goal progress data into a Pandas DataFrame."""
    if not progress:
        return pd.DataFrame()
    
    formatted_data = [{
        "Metric": "Best Pace (km/h)",
        "Value": progress.get("best_pace", "N/A")
    },
    {
        "Metric": "Rolling Avg Pace (km/h)",
        "Value": progress.get("rolling_average_pace", "N/A")
    },
    {
        "Metric": "Target Time (min)",
        "Value": progress.get("target_time", "N/A")
    }]
    
    df = pd.DataFrame(formatted_data)
    df = df.set_index("Metric")
    return df

def format_runs_with_splits_table(runs):
    """Formats run data with split data and returns a list of dicts for charting."""
    if runs.empty:
        return []

    formatted_runs = []
    for index, run in runs.iterrows():
      
      # Fetch split data for this run
      splits_data = fetch_splits_from_db(run['id'])
      
      if splits_data:
          split_paces = {f'Split {split[2]}_Pace': split[4] / 60 if split[4] else None for split in splits_data }
          split_heartrates = {f'Split {split[2]}_Heart Rate': split[8]  if split[8] else None for split in splits_data }
      else:
         split_paces = {}
         split_heartrates = {}
      
      # Convert start_date_local to datetime object and format it
      if run['start_date_local']:
         # Create a timezone-naive datetime object
         local_dt = pd.to_datetime(run['start_date_local'])
         formatted_date = local_dt.strftime('%Y-%m-%d %H:%M:%S')
      else:
          formatted_date = None
      formatted_run = {
            'Date': formatted_date,
            'Distance': run['distance'],
            'moving_time':  f"{int(run['moving_time'] // 60)}:{int(run['moving_time'] % 60):02d}" if run['moving_time'] else None,
            'pace': run['distance'] / (run['moving_time'] / 3600) if run['moving_time'] and run['distance'] else None,
            'average_heartrate': run['average_heartrate'],
            'max_heartrate': run['max_heartrate'],
            'city_name': run['city_name'],
            'temperature': run['temperature'],
            'humidity': run['humidity'],
            **split_paces,
            **split_heartrates
      }
      print(f"Formatted Run: {formatted_run}") # Debug print
      formatted_runs.append(formatted_run)
    return formatted_runs

def fetch_splits_from_db(activity_id):
    """Fetches splits data from the database for a given activity ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM splits_data WHERE activity_id = ?", (activity_id,))
    data = cursor.fetchall()
    conn.close()
    return data

def create_split_pace_chart(formatted_runs):
    """Creates a line chart for split paces."""
    if not formatted_runs:
        return None
    
    fig = go.Figure()
    
    for run_data in formatted_runs:
      split_names = [key for key in run_data if key.startswith('Split ') and "Pace" in key]
      split_paces = [run_data[key] for key in split_names]
      
      fig.add_trace(go.Scatter(
          x=split_names,
          y=split_paces,
          mode='lines+markers',
          name=run_data['Date'],
          hovertemplate="Pace: %{y:.2f} min/km<br>Split: %{x}<extra></extra>"
      ))
    
    fig.update_layout(
        title=dict(
            text="Split Pace Comparison",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Split",
        yaxis_title="Pace (min/km)",
        hovermode='x unified'
    )
    
    return fig

def create_split_heartrate_chart(formatted_runs):
    """Creates a line chart for split heart rates."""
    if not formatted_runs:
        return None

    fig = go.Figure()

    for run_data in formatted_runs:
        split_names = [key for key in run_data if key.startswith('Split ') and "Heart Rate" in key]
        split_heartrates = [run_data[key] for key in split_names]

        fig.add_trace(go.Scatter(
            x=split_names,
            y=split_heartrates,
            mode='lines+markers',
            name=run_data['Date'],
            hovertemplate="Heart Rate: %{y:.0f} bpm<br>Split: %{x}<extra></extra>"
        ))

    fig.update_layout(
        title=dict(
            text="Split Heart Rate Comparison",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Split",
        yaxis_title="Heart Rate (bpm)",
        hovermode='x unified'
    )

    return fig