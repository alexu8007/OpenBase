# app/cli.py

import argparse
import logging
from .scraper import get_weather_forecast, check_for_rain

def main():
    """Main function to run the umbrella reminder CLI."""
    parser = argparse.ArgumentParser(description="Check for rain in the forecast and get an umbrella reminder.")
    parser.add_argument('--lat', type=float, default=40.7128, help='Latitude for the weather forecast location.')
    parser.add_argument('--lon', type=float, default=-74.0060, help='Longitude for the weather forecast location.')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging.')
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("Checking for rain in the forecast...")
    html_content = get_weather_forecast(args.lat, args.lon)
    
    if html_content:
        if check_for_rain(html_content):
            logging.info("Yes, it's going to rain. Don't forget your umbrella! ☔")
        else:
            logging.info("No rain expected. You can leave the umbrella at home. ☀️")

if __name__ == "__main__":
    main() 