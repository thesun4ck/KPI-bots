import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "1063802362").split(",")]

DEFAULT_REMINDER_TIME = "21:00"
DEFAULT_ALERT_THRESHOLD = 30.0
DEFAULT_TIMEZONE = "Europe/Moscow"
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.sqlite")