
# umbrella_reminder/providers/openweathermap.py

import requests
import logging
from .base import WeatherProvider
from ..config import AppConfig

class OpenWeatherMapApiProvider(WeatherProvider):
    """
    A weather provider that uses the OpenWeatherMap One Call API 3.0.
    """
    
    BASE_URL = "https://api.openweathermap.org/data/3.0/onecall"

    def __init__(self, config=AppConfig):
        self.api_key = config.get('API_Keys', 'openweathermap', fallback=None)
        if not self.api_key or self.api_key == 'YOUR_API_KEY_HERE':
            raise ValueError("OpenWeatherMap API key is not configured in config.ini")

    def get_weather(self, lat, lon):
        """
        Fetches the daily forecast from the OpenWeatherMap API.
        """
        # We only need the daily forecast to check for rain in the coming days.
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'exclude': 'current,minutely,hourly,alerts',
            'units': 'metric'
        }
        try:
            logging.info(f"Fetching weather data from OpenWeatherMap API for lat={lat}, lon={lon}")
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching weather data from OpenWeatherMap: {e}")
            if e.response is not None:
                logging.error(f"API Response: {e.response.text}")
            return None
        except ValueError:
            logging.error("Failed to parse JSON response from OpenWeatherMap.")
            return None

    def check_for_rain(self, weather_data):
        """
        Parses the JSON response from OpenWeatherMap to check for rain.
        """
        if not weather_data or 'daily' not in weather_data:
            logging.warning("OpenWeatherMap: No daily forecast data available.")
            return False
        
        try:
            for day in weather_data['daily']:
                if 'rain' in day or any(weather['main'].lower() == 'rain' for weather in day['weather']):
                    logging.debug(f"OpenWeatherMap: Rain found in forecast for day: {day.get('dt')}")
                    return True
            
            logging.info("OpenWeatherMap: No rain found in the upcoming daily forecast.")
            return False
        except (KeyError, TypeError) as e:
            logging.error(f"OpenWeatherMap: Failed to parse forecast data: {e}")
            return False 
