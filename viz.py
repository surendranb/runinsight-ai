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
    """Format average metrics into a DataFrame with proper number formatting."""
    formatted_data = []
    
    for metrics, period in zip(avg_metrics_list, periods):
        if metrics:  # Only add if metrics exist
            row = {
                'Period': period,
                'Avg Distance (km)': f"{metrics.get('distance', 0):.2f}",
                'Avg Pace (km/h)': f"{metrics.get('average_speed', 0):.2f}",
                'Avg HR (bpm)': f"{metrics.get('average_heartrate', 0):.0f}",
                'Avg Elevation (m)': f"{metrics.get('total_elevation_gain', 0):.1f}",  # Fixed double colon
                'Avg Temp (°C)': f"{metrics.get('temperature', 0):.1f}",
                'Avg AQI': f"{metrics.get('pollution_aqi', 0):.0f}",
                'Num Runs': metrics.get('num_runs', 0)
            }
            formatted_data.append(row)
    
    df = pd.DataFrame(formatted_data)
    if not df.empty:
        df.set_index('Period', inplace=True)
    return df

def create_trend_chart(df, metric, title):
    """Creates a bar chart for trend analysis."""
    if df.empty:
        return None

    # Create a copy of the dataframe to avoid modifying the original
    df = df.copy()
    
    # Sort by date
    df = df.sort_values('start_date_ist')
    
    fig = go.Figure()
    
    # Configure dark theme
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(
            family="Arial, sans-serif",
            color='white',
            size=12
        )
    )
    
    if metric == 'pace':
        # Convert pace from km/h to min/km for y-axis labels and tooltip
        df['pace_min_km'] = 60 / df['average_speed'] if 'average_speed' in df.columns else None
        
        # Filter out zero, null values and get unique dates
        df = df[df['pace_min_km'].notna() & (df['pace_min_km'] > 0)]
        # Group by date and take the first run of each day
        df = df.groupby('start_date_ist', as_index=False).first()
        
        if not df.empty:
            fig.add_trace(go.Bar(
                x=df['start_date_ist'],
                y=df['pace_min_km'],
                name='Pace',
                marker_color='#00CED1',  # Bright cyan color
                hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br>" +
                             "<b>Pace:</b> %{y:.2f} min/km<extra></extra>"
            ))
            y_axis_label = 'Pace (min/km)'
            
            # Set y-axis range to make trends more visible
            y_min = 0  # Start from 0 for bars
            y_max = df['pace_min_km'].max() * 1.1
            fig.update_yaxes(range=[y_min, y_max])
        
    elif metric == 'distance':
        # Filter out zero, null values and get unique dates
        df = df[df['distance'].notna() & (df['distance'] > 0)]
        # Group by date and take the first run of each day
        df = df.groupby('start_date_ist', as_index=False).first()
        
        if not df.empty:
            fig.add_trace(go.Bar(
                x=df['start_date_ist'],
                y=df['distance'],
                name='Distance',
                marker_color='#00FF7F',  # Bright green color
                hovertemplate="<b>Date:</b> %{x|%Y-%m-%d}<br>" +
                             "<b>Distance:</b> %{y:.2f} km<extra></extra>"
            ))
            y_axis_label = 'Distance (km)'
            
            # Set y-axis range
            y_min = 0  # Start from 0 for bars
            y_max = df['distance'].max() * 1.1
            fig.update_yaxes(range=[y_min, y_max])
    else:
        return None

    # Update layout with improved styling for dark theme
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor='center',
            font=dict(
                size=20,
                color='white'
            )
        ),
        xaxis=dict(
            title="Date",
            gridcolor='rgba(128,128,128,0.2)',  # Subtle grid
            showgrid=True,
            zeroline=False,
            title_font=dict(size=14),
            tickfont=dict(size=12),
            color='white',
            # Only show dates with actual runs
            tickmode='array',
            ticktext=df['start_date_ist'].dt.strftime('%b %d').tolist(),
            tickvals=df['start_date_ist'].tolist()
        ),
        yaxis=dict(
            title=y_axis_label,
            gridcolor='rgba(128,128,128,0.2)',  # Subtle grid
            showgrid=True,
            zeroline=False,
            title_font=dict(size=14),
            tickfont=dict(size=12),
            color='white'
        ),
        showlegend=False,
        hovermode='x unified',
        margin=dict(t=60, r=30, b=50, l=50),
        bargap=0.3  # Add some gap between bars
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
    #   print(f"Formatted Run: {formatted_run}") # Debug print
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

def create_training_calendar(df, selected_month):
    """Creates a training calendar for the selected month."""
    # Filter the DataFrame for the selected month
    start_date = selected_month.replace(day=1)
    end_date = (start_date + pd.offsets.MonthEnd(1)).replace(day=1)
    monthly_data = df[(df['start_date_ist'] >= start_date) & (df['start_date_ist'] < end_date)]

    # Create a calendar matrix
    num_days = (end_date - start_date).days
    num_weeks = (num_days + start_date.weekday()) // 7 + 1  # Calculate number of weeks needed

    # Initialize a DataFrame to hold the calendar data
    calendar_data = pd.DataFrame(index=range(num_weeks), columns=range(7))

    # Fill the calendar data with distances
    for index, row in monthly_data.iterrows():
        day_of_week = row['start_date_ist'].weekday()
        week_of_month = (row['start_date_ist'].day + start_date.weekday()) // 7
        calendar_data.at[week_of_month, day_of_week] = row['distance']

    # Fill NaN values with 0 for days without runs
    calendar_data.fillna(0, inplace=True)

    # Create a heatmap figure
    fig = go.Figure(data=go.Heatmap(
        z=calendar_data.values,
        x=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        y=[f'Week {i+1}' for i in range(num_weeks)],
        colorscale='Viridis'
    ))

    fig.update_layout(
        title='Training Calendar',
        xaxis_title='Days of the Week',
        yaxis_title='Weeks',
        coloraxis_colorbar=dict(title='Distance (km)')
    )

    return fig

def create_distance_distribution(df, selected_month):
    """Creates a histogram of run distances."""
    if df.empty:
        return None
        
    # Filter data for selected month
    mask = (df['start_date_ist'].dt.year == selected_month.year) & \
           (df['start_date_ist'].dt.month == selected_month.month)
    month_data = df[mask].copy()
    
    if month_data.empty:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=month_data['distance'],
        nbinsx=10,
        name='Distance Distribution'
    ))
    
    fig.update_layout(
        title="Distance Distribution",
        xaxis_title="Distance (km)",
        yaxis_title="Number of Runs",
        showlegend=False
    )
    
    return fig

def create_time_distribution(df, selected_month):
    """Creates a chart showing distribution of run times during the day."""
    if df.empty:
        return None
        
    # Filter data for selected month
    mask = (df['start_date_ist'].dt.year == selected_month.year) & \
           (df['start_date_ist'].dt.month == selected_month.month)
    month_data = df[mask].copy()
    
    if month_data.empty:
        return None
    
    # Extract hour of day
    month_data['hour'] = month_data['start_date_ist'].dt.hour
    
    # Create hour distribution
    hour_dist = month_data.groupby('hour').size()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hour_dist.index,
        y=hour_dist.values,
        name='Time Distribution'
    ))
    
    fig.update_layout(
        title="Running Time Distribution",
        xaxis_title="Hour of Day",
        yaxis_title="Number of Runs",
        showlegend=False
    )
    
    return fig

def create_long_term_trend(df, metric):
    """Creates a line chart showing long-term trends."""
    if df.empty:
        return None
    
    # Resample data weekly
    weekly_data = df.set_index('start_date_ist').resample('W').agg({
        'distance': 'sum',
        'average_speed': 'mean'
    }).reset_index()
    
    fig = go.Figure()
    
    if metric == "Weekly Distance":
        y_data = weekly_data['distance']
        title = "Weekly Distance Trend"
        y_label = "Distance (km)"
    elif metric == "Average Pace":
        y_data = weekly_data['average_speed']
        title = "Average Pace Trend"
        y_label = "Pace (km/h)"
    else:  # Training Load
        # Calculate weekly training load
        weekly_data['training_load'] = weekly_data.apply(
            lambda row: row['distance'] * 150,  # Simplified training load calculation
            axis=1
        )
        y_data = weekly_data['training_load']
        title = "Training Load Trend"
        y_label = "Training Load"
    
    fig.add_trace(go.Scatter(
        x=weekly_data['start_date_ist'],
        y=y_data,
        mode='lines+markers'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        showlegend=False
    )
    
    return fig

def create_detailed_split_chart(splits_data):
    """Creates a detailed chart showing split paces with additional metrics."""
    if not splits_data:
        return None
    
    # Convert splits data to DataFrame
    df = pd.DataFrame(splits_data, columns=[
        'id', 'activity_id', 'split', 'distance', 'elapsed_time',
        'average_speed', 'elevation_difference', 'moving_time',
        'average_heartrate', 'average_grade_adjusted_speed'
    ])
    
    fig = go.Figure()
    
    # Add pace line
    fig.add_trace(go.Scatter(
        x=df['split'],
        y=df['average_speed'],
        mode='lines+markers',
        name='Pace',
        line=dict(color='blue'),
        hovertemplate="Split: %{x}<br>Pace: %{y:.2f} km/h<extra></extra>"
    ))
    
    # Add grade adjusted pace
    fig.add_trace(go.Scatter(
        x=df['split'],
        y=df['average_grade_adjusted_speed'],
        mode='lines+markers',
        name='Grade Adjusted Pace',
        line=dict(color='green', dash='dot'),
        hovertemplate="Split: %{x}<br>Grade Adjusted: %{y:.2f} km/h<extra></extra>"
    ))
    
    fig.update_layout(
        title="Split Analysis",
        xaxis_title="Split Number",
        yaxis_title="Pace (km/h)",
        hovermode='x unified'
    )
    
    return fig

def create_pace_elevation_chart(activity_data, splits_data):
    """Creates a pace elevation chart."""
    if activity_data.empty or not splits_data:
        return None  # Ensure to return None if there's no data

    fig = go.Figure()

    # Check if splits_data is a list of dictionaries
    if isinstance(splits_data, list):
        elevations = [split['elevation'] for split in splits_data if 'elevation' in split]
        paces = [split['pace'] for split in splits_data if 'pace' in split]
    else:
        # If it's a DataFrame, access it normally
        elevations = splits_data['elevation']
        paces = splits_data['pace']

    fig.add_trace(go.Scatter(
        x=elevations,
        y=paces,
        mode='lines+markers'
    ))

    fig.update_layout(
        title="Pace vs Elevation",
        xaxis_title="Elevation (m)",
        yaxis_title="Pace (min/km)"
    )

    return fig

def create_runs_comparison_chart(similar_runs, current_run):
    """Creates a comparison chart between similar runs."""
    fig = go.Figure()
    
    for _, run in similar_runs.iterrows():
        fig.add_trace(go.Scatter(
            x=list(range(1, int(run['distance']) + 1)),
            y=[run['average_speed']] * int(run['distance']),
            name=run['start_date_ist'].strftime('%Y-%m-%d'),
            line=dict(color='rgba(100,100,100,0.2)')
        ))
    
    # Add current run
    fig.add_trace(go.Scatter(
        x=list(range(1, int(current_run['distance']) + 1)),
        y=[current_run['average_speed']] * int(current_run['distance']),
        name='Current Run',
        line=dict(color='blue', width=3)
    ))
    
    fig.update_layout(
        title="Comparison with Similar Runs",
        xaxis_title="Distance (km)",
        yaxis_title="Pace (km/h)",
        showlegend=True
    )
    
    return fig

def create_heart_rate_zones_chart(hr_zones):
    """Creates a bar chart showing heart rate zone distribution."""
    if not hr_zones or not hr_zones['zones']:
        return None
    
    zones = hr_zones['zones']
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(zones.keys()),
            y=list(zones.values()),
            text=list(zones.values()),
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Heart Rate Zone Distribution",
        xaxis_title="Heart Rate Zones",
        yaxis_title="Number of Activities",
        showlegend=False,
        bargap=0.2
    )
    
    return fig

def create_pace_zones_chart(pace_zones):
    """Creates a bar chart showing pace zone distribution."""
    if not pace_zones or not pace_zones['zones']:
        return None
    
    zones = pace_zones['zones']
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(zones.keys()),
            y=list(zones.values()),
            text=list(zones.values()),
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Pace Zone Distribution",
        xaxis_title="Pace Zones",
        yaxis_title="Number of Activities",
        showlegend=False,
        bargap=0.2
    )
    
    return fig

def create_health_trend_chart(df, metric):
    """Creates a line chart showing health-related trends."""
    if df.empty:
        return None
    
    # Resample data weekly
    weekly_data = df.set_index('start_date_ist').resample('W').agg({
        'distance': 'sum',
        'average_speed': 'mean',
        'average_heartrate': 'mean',
        'moving_time': 'sum'
    }).reset_index()
    
    fig = go.Figure()
    
    if metric == "Training Load":
        # Calculate training load (distance * intensity factor)
        weekly_data['training_load'] = weekly_data['distance'] * (weekly_data['average_speed'] / weekly_data['average_speed'].mean())
        y_data = weekly_data['training_load']
        title = "Training Load Trend"
        y_label = "Training Load"
    
    elif metric == "Recovery Rate":
        # Calculate recovery rate based on training frequency
        weekly_data['recovery_rate'] = 100 - (weekly_data['moving_time'] / (7 * 24 * 60 * 60) * 100)
        y_data = weekly_data['recovery_rate']
        title = "Recovery Rate Trend"
        y_label = "Recovery Rate (%)"
    
    else:  # Intensity Distribution
        # Calculate high intensity ratio
        weekly_data['intensity_ratio'] = weekly_data['average_speed'] / weekly_data['average_speed'].mean()
        y_data = weekly_data['intensity_ratio'] * 100
        title = "Intensity Distribution Trend"
        y_label = "Intensity Ratio (%)"
    
    fig.add_trace(go.Scatter(
        x=weekly_data['start_date_ist'],
        y=y_data,
        mode='lines+markers'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        showlegend=False
    )
    
    return fig

def create_pace_distribution(activity_data, splits_data):
    """Creates a distribution chart of pace based on activity and splits data."""
    if splits_data is None or len(splits_data) == 0:
        return None  # Return None if there's no split data

    # Assuming splits_data is a DataFrame or a list of dictionaries
    pace_data = [split['pace'] for split in splits_data if 'pace' in split]

    if not pace_data:  # Check if pace_data is empty
        return None  # Return None if there's no pace data

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=pace_data, nbinsx=20))

    fig.update_layout(
        title="Pace Distribution",
        xaxis_title="Pace (min/km)",
        yaxis_title="Number of Activities",
        showlegend=False
    )

    return fig