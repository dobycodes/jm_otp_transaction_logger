from config_loader import load_config
from logger import setup_logger
from ui_app import launch_ui

def main():
    config = load_config()
    logger = setup_logger("otp_utility")
    logger.info("Launching OTP Utility UI")
    launch_ui()

if __name__ == "__main__":
    main()
