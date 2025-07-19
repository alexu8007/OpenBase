# umbrella_reminder/cli.py

import argparse
import logging
import sys
from .core import UmbrellaApp

def main():
    """
    The main entry point for the command-line interface.
    """
    parser = argparse.ArgumentParser(
        description="Check for rain and get an umbrella reminder.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'location', 
        nargs='?', 
        default=None,
        help='The location to check (e.g., "City, Country" or "latitude,longitude").\nIf not provided, the default from config.ini is used.'
    )
    
    parser.add_argument(
        '--verbose', 
        '-v', 
        action='store_true', 
        help='Enable verbose logging for debugging.'
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        app = UmbrellaApp()
        app.run(location_str=args.location)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        logging.error(f"Application Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"An unexpected critical error occurred: {e}", exc_info=args.verbose)
        sys.exit(1)

if __name__ == "__main__":
    main() 