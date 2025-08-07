import logging
from pathlib import Path
from datetime import datetime
import shutil

def setup_logger(name="gmail_fetcher", log_file="logs/debug.log", level=logging.INFO):
    # Ensure the logs directory exists
    Path("logs").mkdir(exist_ok=True)

    # Monday log rotation: backup and truncate
    if datetime.today().weekday() == 0:  # Monday = 0
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            backup_file = f"logs/debug_{timestamp}.log"
            shutil.copy2(log_file, backup_file)
            Path(log_file).write_text("")  # Truncate
        except FileNotFoundError:
            # If log_file doesn't exist yet, it's okay to skip rotation
            pass
        except Exception as e:
            print(f"Log rotation failed: {e}")

    # Format for each log entry
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Create file handler with UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent adding multiple handlers on repeated calls
    if not logger.hasHandlers():
        logger.addHandler(file_handler)

    return logger
