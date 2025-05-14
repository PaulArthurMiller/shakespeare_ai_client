import logging
import os
from datetime import datetime

class CustomLogger:
    """A custom logging class that provides standardized logging functionality."""
    
    def __init__(self, name, log_level='DEBUG', log_file=None):
        """
        Initialize the CustomLogger.
        
        Args:
            name (str): The name of the logger
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file (str, optional): Path to the log file. If None, logs to console only.
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if log_file specified)
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _log(self, message: str, level: str = "info") -> None:
        """
        Log a message at the specified level.
        
        Args:
            message: Message to log
            level: Log level (info, error, warning, debug)
        """
        if level.lower() == "error":
            self.logger.error(message)
        elif level.lower() == "warning":
            self.logger.warning(message)
        elif level.lower() == "debug":
            self.logger.debug(message)
        else:  # Default to info
            self.logger.info(message)
    
    def info(self, message: str) -> None:
        """Log an info message."""
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.logger.warning(message)

    def error(self, message: str) -> None:
        """Log an error message."""
        self.logger.error(message)

    def debug(self, message: str) -> None:
        """Log a debug message."""
        self.logger.debug(message)