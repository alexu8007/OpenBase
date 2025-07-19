
# umbrella_reminder/providers/nws.py

import requests
from bs4 import BeautifulSoup
import logging
from .base import WeatherProvider

class NWSScraperProvider(WeatherProvider):
    """
    A weather provider that scrapes data from the National Weather Service (weather.gov).
    """
    
    BASE_URL = "https://forecast.weather.gov/MapClick.php"

    def get_weather(self, lat, lon):
        """
        Fetches the detailed forecast page from weather.gov.
        """
        url = f"{self.BASE_URL}?lat={lat}&lon={lon}"
        try:
            logging.info(f"Fetching weather data from NWS: {url}")
            # NWS requires a User-Agent header
            headers = {'User-Agent': 'UmbrellaReminder/1.0 (https://github.com/user/repo; contact@example.com)'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching weather data from NWS: {e}")
            return None

    def check_for_rain(self, html_content):
        """
        Parses the HTML from a weather.gov forecast page to check for rain.
        """
        if not html_content:
            return False
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forecast_elements = soup.select("#detailed-forecast-body .row .col-sm-10")
            
            for forecast in forecast_elements:
                forecast_text = forecast.get_text().lower()
                # Use a more comprehensive list of precipitation keywords
                if any(keyword in forecast_text for keyword in ["rain", "showers", "thunderstorms", "drizzle", "precipitation"]):
                    logging.debug(f"NWS: Rain keyword found in forecast: '{forecast.get_text().strip()}'")
                    return True
            
            logging.info("NWS: No rain keywords found in the detailed forecast.")
            return False
        except Exception as e:
            logging.error(f"NWS: Failed to parse forecast HTML: {e}")
            return False 
