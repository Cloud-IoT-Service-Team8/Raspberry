# mqtt/model.py

import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

KST = timezone(timedelta(hours=9))
_counter = 0

DEVICE_ID = os.getenv("DEVICE_ID", "rpi-001")
USER_ID = os.getenv("USER_ID", "user-001")


def build_message(
    bio: dict,
    door_distance_cm: float,
    delirium_suspected: bool,
    abnormal_exit: bool,
    door_open: bool,
    rfid_detected: bool,
    buzzer_activated: bool,
) -> dict:
    global _counter
    _counter += 1

    now = datetime.now(KST)
    event_id = f"evt-{now.strftime('%Y%m%d')}-{_counter:04d}"

    severity = "HIGH" if delirium_suspected and abnormal_exit else "LOW"

    return {
        "eventId": event_id,
        "deviceId": DEVICE_ID,
        "userId": USER_ID,
        "eventType": "DELIRIUM_EXIT_RISK",
        "severity": severity,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "deliriumSuspected": delirium_suspected,
        "abnormalExit": abnormal_exit,
        "doorOpen": door_open,
        "rfidDetected": rfid_detected,
        "buzzerActivated": buzzer_activated,
        "processedSensorData": {
            "heartRate": bio["heart_rate"],
            "sleepState": bio["sleep_state"],
            "activityLevel": bio["activity_level"],
            "doorDistanceCm": door_distance_cm,
        },
    }