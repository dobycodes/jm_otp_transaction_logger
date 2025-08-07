import json
import os
from logger import setup_logger

logger = setup_logger(name="config_loader")

CONFIG_PATH = "config.json"

REQUIRED_KEYS = {
    "spreadsheet_id": str,
    "tab_mapping": dict,
    "otp_regex": str,
    "transaction_log_excel_path": str,
    "sheets_credentials_path": str,
    "gmail_credentials_path": str
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError("Missing config.json file")

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    validate_config(config)
    return config

def validate_config(config):
    for key, expected_type in REQUIRED_KEYS.items():
        if key not in config:
            raise KeyError(f"Missing required config key: {key}")
        if not isinstance(config[key], expected_type):
            raise TypeError(f"Config key '{key}' must be of type {expected_type.__name__}")

    # Optional: log loaded keys for traceability
    # logger.info(f"Config loaded successfully with keys: {list(config.keys())}")
