import logging
import os

class Logger:
    
    def __init__(self):
        self.setup_logging()

    def setup_logging(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(plugin_dir)

        # Create a logs folder if it doesn't exist
        logs_dir = os.path.join(parent_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # Create a logger
        self.logger = logging.getLogger("KgrFinder")

        # Set the log level based on the environment
        if os.environ.get('KGR') == 'development':
            self.logger.setLevel(logging.DEBUG)  
        else:
            self.logger.setLevel(logging.INFO)


        # Create a file handler in the logs folder
        log_file = os.path.join(logs_dir, "kgrfinder.log")
        file_handler = logging.FileHandler(log_file)
        # Set the formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)

        # Add the handler to the logger
        self.logger.addHandler(file_handler)

    def log_info(self, message):
        self.logger.info(f"KGR Plugin: {message}")

    def log_debug(self, message):
        self.logger.debug(f"KGR Plugin: {message}")

    def log_error(self, message):
        self.logger.error(f"KGR Plugin: {message}")
