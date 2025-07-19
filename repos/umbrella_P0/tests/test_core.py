# tests/test_core.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
import configparser

# Mock the config before other imports to prevent FileNotFoundError
@pytest.fixture(autouse=True)
def mock_config():
    config = configparser.ConfigParser()
    config['App'] = {'provider': 'nws'}
    config['Location'] = {'default_location': '123,456'}
    config['Caching'] = {'enabled': 'false', 'ttl': '600'}
    config['Notifications'] = {'notifiers': 'console'}
    config['SMTP'] = {
        'host': 'smtp.example.com', 'port': '587', 'username': 'user', 'password': 'pass',
        'from_address': 'from@example.com', 'to_address': 'to@example.com', 'use_tls': 'true'
    }
    with patch('umbrella_reminder.config.AppConfig', config):
        yield

# Now we can import the classes that depend on the config
from umbrella_reminder.core import UmbrellaApp

@patch('umbrella_reminder.core.Geocoder')
@patch('umbrella_reminder.core.Cache')
@patch('umbrella_reminder.core.NWSScraperProvider')
@patch('umbrella_reminder.core.ConsoleNotifier')
def test_app_run_rain(MockConsoleNotifier, MockNWSProvider, MockCache, MockGeocoder):
    """
    Tests the main run loop when rain is expected.
    """
    # Arrange
    mock_geocoder_instance = MockGeocoder.return_value
    mock_geocoder_instance.get_coords.return_value = (10, 20)

    mock_provider_instance = MockNWSProvider.return_value
    mock_provider_instance.get_weather.return_value = "Some weather data"
    mock_provider_instance.check_for_rain.return_value = True

    mock_cache_instance = MockCache.return_value
    mock_cache_instance.get.return_value = None # Cache miss

    mock_notifier_instance = MockConsoleNotifier.return_value

    # Act
    app = UmbrellaApp()
    app.run(location_str="Test Location")

    # Assert
    mock_geocoder_instance.get_coords.assert_called_once_with("Test Location")
    mock_cache_instance.get.assert_called_once()
    mock_provider_instance.get_weather.assert_called_once_with(10, 20)
    mock_cache_instance.set.assert_called_once_with(
        'NWSScraperProvider-10.0000-20.0000', "Some weather data"
    )
    mock_provider_instance.check_for_rain.assert_called_once_with("Some weather data")
    mock_notifier_instance.send.assert_called_once_with(
        "Yes, it's going to rain. Don't forget your umbrella! ☔"
    )

@patch('umbrella_reminder.core.Geocoder')
@patch('umbrella_reminder.core.Cache')
@patch('umbrella_reminder.core.NWSScraperProvider')
@patch('umbrella_reminder.core.ConsoleNotifier')
def test_app_run_no_rain_from_cache(MockConsoleNotifier, MockNWSProvider, MockCache, MockGeocoder):
    """
    Tests the main run loop when no rain is expected, and the data is cached.
    """
    # Arrange
    mock_geocoder_instance = MockGeocoder.return_value
    mock_geocoder_instance.get_coords.return_value = (10, 20)
    
    mock_provider_instance = MockNWSProvider.return_value
    mock_provider_instance.check_for_rain.return_value = False # No rain

    mock_cache_instance = MockCache.return_value
    mock_cache_instance.get.return_value = "Cached weather data" # Cache hit

    mock_notifier_instance = MockConsoleNotifier.return_value

    # Act
    app = UmbrellaApp()
    app.run(location_str="Test Location")

    # Assert
    mock_provider_instance.get_weather.assert_not_called() # Should not fetch new data
    mock_cache_instance.set.assert_not_called() # Should not set cache again
    mock_provider_instance.check_for_rain.assert_called_once_with("Cached weather data")
    mock_notifier_instance.send.assert_called_once_with(
        "No rain expected. You can leave the umbrella at home. ☀️"
    ) 