# umbrella_reminder/notifiers/email.py

import logging
import smtplib
from email.mime.text import MIMEText
from .base import Notifier

class EmailNotifier(Notifier):
    """
    A notifier that sends messages via email using SMTP.
    """

    def __init__(self, config):
        super().__init__(config)
        try:
            self.smtp_host = config.get('SMTP', 'host')
            self.smtp_port = config.getint('SMTP', 'port')
            self.smtp_user = config.get('SMTP', 'username')
            self.smtp_password = config.get('SMTP', 'password')
            self.from_address = config.get('SMTP', 'from_address')
            self.to_address = config.get('SMTP', 'to_address')
            self.use_tls = config.getboolean('SMTP', 'use_tls')
        except (KeyError, ValueError) as e:
            raise ValueError(f"SMTP configuration is missing or invalid in config.ini: {e}")

    def send(self, message):
        """
        Sends a notification message via email.
        
        Args:
            message (str): The message to send.
            
        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        logging.info(f"Attempting to send email notification to {self.to_address}")
        
        msg = MIMEText(message)
        msg['Subject'] = 'Umbrella Reminder'
        msg['From'] = self.from_address
        msg['To'] = self.to_address

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_address, [self.to_address], msg.as_string())
            logging.info("Email notification sent successfully.")
            return True
        except smtplib.SMTPException as e:
            logging.error(f"Failed to send email notification: {e}")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred while sending email: {e}")
            return False 