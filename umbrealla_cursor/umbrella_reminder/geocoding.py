# umbrella_reminder/geocoding.py

import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

class Geocoder:
    """
    Handles converting location strings (like "City, Country") into
    latitude and longitude coordinates.
    """
    
    def __init__(self):
        # A unique user-agent is required by Nominatim's terms of service.
        self.geolocator = Nominatim(user_agent="umbrella_reminder_app/1.0")

    def get_coords(self, location_str):
        """
        Converts a location string to a (latitude, longitude) tuple.

        Args:
            location_str (str): The location name (e.g., "London, UK").

        Returns:
            tuple: A (latitude, longitude) tuple or None if geocoding fails.
        """
        # First, check if the input is already in "lat,lon" format
        try:
            if ',' in location_str:
                lat, lon = map(float, location_str.split(','))
                logging.debug(f"Input '{location_str}' is already in coordinate format.")
                return lat, lon
        except (ValueError, IndexError):
            # Not in coordinate format, proceed with geocoding
            pass
            
        logging.info(f"Geocoding location: '{location_str}'")
        try:
            location = self.geolocator.geocode(location_str)
            if location:
                logging.info(f"Found '{location.address}' at ({location.latitude}, {location.longitude})")
                return location.latitude, location.longitude
            else:
                logging.error(f"Could not geocode location: '{location_str}'. No results found.")
                return None
        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logging.error(f"Geocoding service timed out or is unavailable: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during geocoding: {e}")
            return None 