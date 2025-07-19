# umbrella_reminder/notifiers/base.py

from abc import ABC, abstractmethod

class Notifier(ABC):
    """
    Abstract base class for all notifiers.
    
    This class defines the interface that all concrete notifiers must implement.
    """
    
    def __init__(self, config):
        """
        Initializes the notifier with application configuration.

        Args:
            config (configparser.ConfigParser): The application configuration.
        """
        self.config = config

    @abstractmethod
    def send(self, message):
        """
        Sends a notification message.

        Args:
            message (str): The message to send.
        """
        pass 