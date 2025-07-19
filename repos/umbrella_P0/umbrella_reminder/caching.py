# umbrella_reminder/caching.py

import json
import logging
import time
from pathlib import Path

class Cache:
    """
    A simple file-based JSON cache to store weather data.
    """
    
    def __init__(self, config):
        self.enabled = config.getboolean('Caching', 'enabled', fallback=False)
        self.ttl = config.getint('Caching', 'ttl', fallback=600)
        
        # Define cache directory path
        self.cache_dir = Path.home() / '.cache' / 'umbrella-reminder'
        if self.enabled:
            # Create cache directory if it doesn't exist
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Cache enabled. TTL: {self.ttl}s. Directory: {self.cache_dir}")

    def _get_cache_filepath(self, key):
        """Generates a filepath for a given cache key."""
        return self.cache_dir / f"{key}.json"

    def get(self, key):
        """
        Retrieves an item from the cache if it exists and is not expired.
        """
        if not self.enabled:
            return None

        cache_file = self._get_cache_filepath(key)
        
        if not cache_file.exists():
            logging.debug(f"Cache miss for key: {key}")
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            if time.time() - data['timestamp'] > self.ttl:
                logging.info(f"Cache expired for key: {key}")
                self.delete(key)
                return None
            
            logging.info(f"Cache hit for key: {key}")
            return data['payload']
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning(f"Invalid cache file for key {key}: {e}. Deleting.")
            self.delete(key)
            return None

    def set(self, key, payload):
        """
        Saves an item to the cache.
        """
        if not self.enabled:
            return

        cache_file = self._get_cache_filepath(key)
        data = {
            'timestamp': time.time(),
            'payload': payload
        }
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            logging.info(f"Cache set for key: {key}")
        except IOError as e:
            logging.error(f"Failed to write to cache file {cache_file}: {e}")

    def delete(self, key):
        """
        Deletes an item from the cache.
        """
        if not self.enabled:
            return
            
        try:
            cache_file = self._get_cache_filepath(key)
            if cache_file.exists():
                cache_file.unlink()
                logging.debug(f"Cache deleted for key: {key}")
        except IOError as e:
            logging.error(f"Failed to delete cache file for key {key}: {e}") 