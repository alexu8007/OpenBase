
# app/scraper.py

import requests
from bs4 import BeautifulSoup
import logging
from .config import BASE_WEATHER_URL

def get_weather_forecast(lat, lon):
    """Fetches the weather forecast for a given latitude and longitude."""
    url = f"{BASE_WEATHER_URL}?lat={lat}&lon={lon}"
    try:
        logging.info(f"Fetching weather data from {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching weather data: {e}")
        return None

def check_for_rain(html_content):
    """Parses the HTML content to check if rain is in the forecast."""
    if not html_content:
        return False
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    forecast_elements = soup.select("#detailed-forecast-body .row .col-sm-10")
    
    for forecast in forecast_elements:
        forecast_text = forecast.get_text().lower()
        if "rain" in forecast_text or "showers" in forecast_text or "thunderstorms" in forecast_text:
            logging.debug(f"Rain keyword found in forecast: '{forecast.get_text().strip()}'")
            return True
            
    return False 
