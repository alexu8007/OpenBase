# umbrella_reminder/providers/base.py

from abc import ABC, abstractmethod

class WeatherProvider(ABC):
    """
    Abstract base class for all weather providers.
    
    This class defines the interface that all concrete weather providers must implement.
    """
    
    @abstractmethod
    def get_weather(self, lat, lon):
        """
        Fetches weather data for a given latitude and longitude.

        Args:
            lat (float): The latitude.
            lon (float): The longitude.

        Returns:
            str: A textual description of the weather forecast.
                 Returns None if fetching fails.
        """
        pass

    @abstractmethod
    def check_for_rain(self, weather_data):
        """
        Parses the weather data to check for rain.

        Args:
            weather_data (any): The data returned by get_weather. 
                                The type depends on the provider.

        Returns:
            bool: True if rain is in the forecast, False otherwise.
        """
        pass 