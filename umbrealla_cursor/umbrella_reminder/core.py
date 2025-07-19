# umbrella_reminder/core.py

import logging
from .config import AppConfig
from .caching import Cache
from .geocoding import Geocoder
from .providers.nws import NWSScraperProvider
from .providers.openweathermap import OpenWeatherMapApiProvider
from .notifiers.console import ConsoleNotifier
from .notifiers.email import EmailNotifier

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

    def __init__(self):
        if not AppConfig:
            raise RuntimeError("Configuration could not be loaded. Please ensure config.ini exists.")
        
        self.config = AppConfig
        self.cache = Cache(self.config)
        self.geocoder = Geocoder()
        self.provider = self._initialize_provider()
        self.notifiers = self._initialize_notifiers()

    def _initialize_provider(self):
        """Initializes the weather provider based on the configuration."""
        provider_name = self.config.get('App', 'provider', fallback='nws').lower()
        provider_class = self.PROVIDER_CLASSES.get(provider_name)
        
        if not provider_class:
            raise ValueError(f"Unsupported weather provider: {provider_name}")
            
        logging.info(f"Using weather provider: {provider_name}")
        return provider_class()

    def _initialize_notifiers(self):
        """Initializes a list of notifiers based on the configuration."""
        notifiers = []
        notifier_names_str = self.config.get('Notifications', 'notifiers', fallback='console')
        notifier_names = [name.strip().lower() for name in notifier_names_str.split(',')]
        
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

    def run(self, location_str=None):
        """
        Executes the main logic of the application.
        
        Args:
            location_str (str, optional): The location to check. Overrides the config default.
        """
        if not location_str:
            location_str = self.config.get('Location', 'default_location')
            logging.info(f"No location provided, using default: '{location_str}'")

        coords = self.geocoder.get_coords(location_str)
        if not coords:
            logging.error("Could not determine coordinates for the location. Aborting.")
            return

        lat, lon = coords
        cache_key = f"{self.provider.__class__.__name__}-{lat:.4f}-{lon:.4f}"
        
        # Check cache first
        weather_data = self.cache.get(cache_key)
        if not weather_data:
            weather_data = self.provider.get_weather(lat, lon)
            if weather_data:
                self.cache.set(cache_key, weather_data)

        if not weather_data:
            logging.error("Failed to get weather data from the provider. Aborting.")
            return

        if self.provider.check_for_rain(weather_data):
            message = "Yes, it's going to rain. Don't forget your umbrella! ☔"
        else:
            message = "No rain expected. You can leave the umbrella at home. ☀️"
            
        self.send_notifications(message)

    def send_notifications(self, message):
        """Sends the message using all configured notifiers."""
        if not self.notifiers:
            logging.warning("No notifiers configured. Cannot send notification.")
            return
            
        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception as e:
                logging.error(f"Failed to send notification using {notifier.__class__.__name__}: {e}") 