from abc import ABC, abstractmethod
import json
import requests
from google.generativeai import GenerativeModel, configure as genai_configure

class LLMService:
    """Base class for LLM services"""
    
    def _create_prompt(self, last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config):
        """Create prompt for LLM services"""
        # Calculate pace in km/h
        last_activity_pace = last_activity['distance'] / (last_activity['elapsed_time'] / 3600) if last_activity['elapsed_time'] and last_activity['distance'] else None
        
        def safe_get_metric(table, period, column, default='N/A'):
            """Safely get metric from the formatted table."""
            try:
                return table.loc[period, column]
            except (KeyError, AttributeError):
                return default

        return f"""
            Goal: {goal_config["goal"]}
            
            Analyze the user's last run compared to their recent averages:
            
            Last Run:
            - Distance: {last_activity.get('distance', 'N/A')} km
            - Pace: {last_activity_pace if last_activity_pace else 'N/A'} km/h
            - Avg Heart Rate: {last_activity.get('average_heartrate', 'N/A')} bpm
            - Elevation: {last_activity.get('total_elevation_gain', 'N/A')} meters
            - Temperature: {last_activity.get('temperature', 'N/A')} °C
            - AQI: {last_activity.get('pollution_aqi', 'N/A')}
           
            Averages:
            - Last 7 Days:
                - Distance: {safe_get_metric(formatted_avg_table, 'Last 7 Days', 'Avg Distance (km)')} km
                - Pace: {safe_get_metric(formatted_avg_table, 'Last 7 Days', 'Avg Pace (km/h)')} km/h
                - Avg Heart Rate: {safe_get_metric(formatted_avg_table, 'Last 7 Days', 'Avg HR (bpm)')} bpm
                - Elevation: {safe_get_metric(formatted_avg_table, 'Last 7 Days', 'Avg Elevation (m)')} meters
                - Temperature: {safe_get_metric(formatted_avg_table, 'Last 7 Days', 'Avg Temp (°C)')} °C
                - AQI: {safe_get_metric(formatted_avg_table, 'Last 7 Days', 'Avg AQI')}
            
            Volume Goal Progress (2025):
            - Total Distance: {volume_progress.get('total_distance', {}).get('progress', 'N/A')} / {volume_progress.get('total_distance', {}).get('goal', 'N/A')} km
            { ' '.join([f"- Number of {k.split('_')[1].replace('km','')}km Runs: {v.get('progress', 'N/A')} / {v.get('goal', 'N/A')}" for k,v in volume_progress.items() if k.startswith('runs_')])}
            
            Performance Goal Progress:
            - Best Pace: {performance_progress.get('best_pace', 'N/A') if performance_progress.get('best_pace') is not None else 'N/A'} km/h
            - Rolling Average Pace (last 10 runs): {performance_progress.get('rolling_average_pace', 'N/A') if performance_progress.get('rolling_average_pace') is not None else 'N/A'} km/h
            - Target Time: {performance_progress.get('target_time', 'N/A')} min
            
            Based on this data, provide specific and actionable recommendations to help the user achieve their goal.
        """

    def generate_insight(self, last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config):
        """Generate running insights based on activity data and goals."""
        raise NotImplementedError("Subclasses must implement generate_insight")

class GeminiService(LLMService):
    def __init__(self, api_key):
        genai_configure(api_key=api_key)
        self.model = GenerativeModel('gemini-2.0-pro-exp-02-05')
    
    def generate_insight(self, last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config):
        """Generate running insights based on activity data and goals."""
        try:
            prompt = self._create_prompt(last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config)
            response = self.model.generate_content(prompt)
            return response.parts[0].text if response.parts else None
        except Exception as e:
            return f"Error generating insight: {str(e)}"

class OllamaService(LLMService):
    def __init__(self, model_name="deepseek-r1"):
        self.model_name = model_name
        self.api_url = "http://localhost:11434/api/generate"
        
    def generate_insight(self, last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config):
        try:
            prompt = self._create_prompt(last_activity, formatted_avg_table, volume_progress, performance_progress, goal_config)
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(self.api_url, json=payload)
            if response.status_code == 200:
                return response.json().get('response')
            else:
                return f"Error: HTTP {response.status_code}"
        except Exception as e:
            return f"Error generating insight: {str(e)}"

def create_llm_service(service_type="gemini", api_key=None, model_name="deepseek-r1"):
    """Factory function to create LLM service"""
    if service_type == "gemini":
        return GeminiService(api_key)
    elif service_type == "ollama":
        return OllamaService(model_name)
    else:
        raise ValueError(f"Unknown LLM service type: {service_type}") 