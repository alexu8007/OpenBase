# umbrella_reminder/config.py

import configparser
import os
from pathlib import Path

def get_config():
    """
    Reads and parses the configuration file.

    It looks for 'config.ini' in the following order:
    1. The current working directory.
    2. The user's home directory (~/.config/umbrella-reminder/config.ini).

    Returns:
        configparser.ConfigParser: The parsed configuration object.
    """
    config = configparser.ConfigParser()
    
    # Define potential config file locations
    current_dir_config = Path.cwd() / 'config.ini'
    home_dir_config = Path.home() / '.config' / 'umbrella-reminder' / 'config.ini'

    if os.path.exists(current_dir_config):
        config_path = current_dir_config
    elif os.path.exists(home_dir_config):
        config_path = home_dir_config
    else:
        # Provide a helpful error message if the config is not found
        raise FileNotFoundError(
            f"Configuration file 'config.ini' not found. "
            f"Please create one at '{current_dir_config}' or '{home_dir_config}'. "
            f"You can use 'config.ini.example' as a template."
        )

    config.read(config_path)
    return config

# Load config once and make it available for import
try:
    AppConfig = get_config()
except FileNotFoundError as e:
    # This allows the app to be imported without a config file,
    # but it will fail if the config is accessed.
    print(f"Warning: {e}")
    AppConfig = None 