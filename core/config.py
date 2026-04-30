from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

@dataclass
class Settings:
    # Fitbit
    fitbit_access_token:  str = os.getenv("FITBIT_ACCESS_TOKEN", "")
    fitbit_refresh_token: str = os.getenv("FITBIT_REFRESH_TOKEN", "")
    fitbit_client_id:     str = os.getenv("FITBIT_CLIENT_ID", "")
    fitbit_client_secret: str = os.getenv("FITBIT_CLIENT_SECRET", "")
    fitbit_api_base:      str = os.getenv("FITBIT_API_BASE", "https://api.fitbit.com")

    # MQTT
    mqtt_broker: str = os.getenv("MQTT_BROKER", "")
    mqtt_port:   int = int(os.getenv("MQTT_PORT", "8883"))
    mqtt_topic:  str = os.getenv("MQTT_TOPIC", "")

    # 장치
    device_id: str = os.getenv("DEVICE_ID", "rpi-001")
    user_id:   str = os.getenv("USER_ID", "user-001")

settings = Settings()