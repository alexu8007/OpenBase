
# umbrella_reminder/core.py

import logging
from .config import AppConfig
from .caching import Cache
from .geocoding import Geocoder
from .providers.nws import NWSScraperProvider
from .providers.openweathermap import OpenWeatherMapApiProvider
from .notifiers.console import ConsoleNotifier
from .notifiers.email import EmailNotifier
from typing import Any, List

class UmbrellaApp:
    """
    The main application class that orchestrates the umbrella reminder process.
    """
    
    PROVIDER_CLASSES = {
        "nws": NWSScraperProvider,
        "openweathermap": OpenWeatherMapApiProvider,
    }
    
    NOTIFIER_CLASSES = {
        "console": ConsoleNotifier,
        "email": EmailNotifier,
    }

    def __init__(self) -> None:
        """
        Initializes the UmbrellaApp instance with configuration and dependencies.
        """
        if not AppConfig:
            raise RuntimeError("Configuration could not be loaded. Please ensure config.ini exists.")
        
        self.config = AppConfig
        self.cache = Cache(self.config)
        self.geocoder = Geocoder()
        self.provider = self._initialize_provider()
        self.notifiers = self._initialize_notifiers()

    def _initialize_provider(self) -> Any:
        """Initializes the weather provider based on the configuration."""
        provider_name = self.config.get('App', 'provider', fallback='nws').lower()
        provider_class = self.PROVIDER_CLASSES.get(provider_name)
        
        if not provider_class:
            raise ValueError(f"Unsupported weather provider: {provider_name}")
            
        logging.info(f"Using weather provider: {provider_name}")
        return provider_class()

    def _initialize_notifiers(self) -> List[Any]:
        """Initializes a list of notifiers based on the configuration."""
        notifiers = []
        notifier_names_str = self.config.get('Notifications', 'notifiers', fallback='console')
        # Generator expression to split and process notifier names
        notifier_names = (name.strip().lower() for name in notifier_names_str.split(','))
        
        for name in notifier_names:
            notifier_class = self.NOTIFIER_CLASSES.get(name)
            if notifier_class:
                try:
                    notifiers.append(notifier_class(self.config))
                    logging.info(f"Enabled notifier: {name}")
                except (ValueError, KeyError) as e:
                    logging.warning(f"Could not initialize notifier '{name}': {e}")
            else:
                logging.warning(f"Unsupported notifier configured: {name}")
        return notifiers

    def fetch_weather_data(self, lat: float, lon: float) -> dict:
        """
        Fetches weather data for the given latitude and longitude, utilizing cache if available.
        """
        cache_key = f"{self.provider.__class__.__name__}-{lat:.4f}-{lon:.4f}"
        weather_data = self.cache.get(cache_key)
        if not weather_data:
            weather_data = self.provider.get_weather(lat, lon)
            if weather_data:
                self.cache.set(cache_key, weather_data)
        return weather_data

    def determine_rain_message(self, weather_data: dict) -> str:
        """
        Determines a message based on whether rain is expected in the weather data.
        """
        # Check if rain is expected using the provider's method
        if self.provider.check_for_rain(weather_data):
            message = "Yes, it's going to rain. Don't forget your umbrella! ☔"
        else:
            message = "No rain expected. You can leave the umbrella at home. ☀️"
        return message

    def _get_location_str(self, location_str: str = None) -> str:
        if not location_str:
            location_str = self.config.get('Location', 'default_location')
            logging.info(f"No location provided, using default: '{location_str}'")
        return location_str

    def _get_coordinates(self, location_str: str) -> tuple[float, float] or None:
        coords = self.geocoder.get_coords(location_str)
        if not coords:
            logging.error("Could not determine coordinates for the location. Aborting.")
        return coords

    def _process_and_notify(self, lat: float, lon: float) -> None:
        weather_data = self.fetch_weather_data(lat, lon)
        if not weather_data:
            logging.error("Failed to get weather data from the provider. Aborting.")
            return
        message = self.determine_rain_message(weather_data)
        self.send_notifications(message)

    def run(self, location_str: str = None) -> None:
        """
        Executes the main logic of the application.
        
        Args:
            location_str (str, optional): The location to check. Overrides the config default.
        """
        location_str = self._get_location_str(location_str)
        coords = self._get_coordinates(location_str)
        if not coords:
            return
        lat, lon = coords
        self._process_and_notify(lat, lon)

    def send_notifications(self, message: str) -> None:
        """Sends the message using all configured notifiers."""
        if not self.notifiers:
            logging.warning("No notifiers configured. Cannot send notification.")
            return
            
        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as e:
                logging.error(f"Failed to send notification using {notifier.__class__.__name__}: {e}") 
