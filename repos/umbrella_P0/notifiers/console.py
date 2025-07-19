# umbrella_reminder/notifiers/console.py

import logging
from .base import Notifier

class ConsoleNotifier(Notifier):
    """
    A notifier that prints messages to the console.
    """

    def send(self, message):
        """
        Sends a notification message to the console using the logging framework.
        
        Args:
            message (str): The message to send.
        """
        logging.info("=" * 30)
        logging.info("UMBRELLA REMINDER")
        logging.info("=" * 30)
        logging.info(message)
        logging.info("=" * 30)
        return True 