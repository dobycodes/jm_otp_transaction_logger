from config_loader import load_config
from logger import setup_logger
from ui_app import launch_ui
from downsync_from_google import pull_from_google_sheet
from sync_to_google import push_to_google_sheet
from downsync_from_google import refresh_transaction_types
from pathlib import Path
import json
import threading

logger = setup_logger("otp_utility")

# 🔧 Load configuration
CONFIG_PATH = Path("config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

MASTER_SHEET_PATH = Path(config["transaction_log_excel_path"])

config = load_config()

def sync_config():
    pull_from_google_sheet()
    refresh_transaction_types(excel_path=MASTER_SHEET_PATH,tab_name="Transaction_Types",json_path=Path("transaction_types.json"))

def background_sync():
    try:
        sync_config()
        logger.info("✅ Background config sync complete")
    except Exception as e:
        logger.warning(f"⚠️ Background sync failed: {e}")

def main():
    
    logger.info("Launching OTP Utility UI")

    # 🚀 Start background sync before launching UI
    threading.Thread(target=background_sync, daemon=True).start()

    launch_ui()

    push_to_google_sheet()

if __name__ == "__main__":
    main()
