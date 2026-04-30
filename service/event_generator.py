# ============================================================
# logic/event_generator.py
# 서버 합의 이벤트 JSON 생성
# ============================================================

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_counter = 0


def create_delirium_event(bio: dict, sensor, state, buzzer_activated: bool, ultrasonic_cm: Optional[float] = None) -> dict:
    global _counter
    _counter += 1

    now      = datetime.now(KST)
    event_id = f"evt-{now.strftime('%Y%m%d')}-{_counter:04d}"

    reasons = []
    if state.abnormal_heart_rate: reasons.append("heart_rate")
    if state.abnormal_sleep:      reasons.append("sleep")
    if state.abnormal_activity:   reasons.append("activity")

    event = {
        "eventId":           event_id,
        "deviceId":          os.getenv("DEVICE_ID", "rpi-001"),
        "userId":            os.getenv("USER_ID", "user-001"),
        "eventType":         "DELIRIUM_EXIT_RISK",
        "severity":          "HIGH",
        "timestamp":         now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "deliriumSuspected": state.delirium_suspected,
        "abnormalExit":      state.abnormal_exit,
        "doorOpen":          sensor.door_open,
        "rfidDetected":      sensor.rfid_authorized,
        "buzzerActivated":   buzzer_activated,
        "processedSensorData": {
            "heartRate":       bio["heart_rate"],
            "sleepState":      bio["sleep_state"],
            "activityLevel":   bio["activity_level"],
            "steps":           bio.get("steps", 0),
            "ultrasonicCm":    ultrasonic_cm,
            "abnormalReasons": reasons,
            "bioTimestamp":    bio.get("timestamp", ""),
        },
    }
    logger.info("[EVENT] 생성 | ID: %s", event_id)
    return event


def create_bio_report(bio: dict, delirium_suspected: bool) -> dict:
    """주기 생체 보고 (섬망 이벤트 아닌 경우)"""
    now = datetime.now(KST)
    return {
        "eventId":           f"bio-{now.strftime('%Y%m%d%H%M%S')}",
        "deviceId":          os.getenv("DEVICE_ID", "rpi-001"),
        "userId":            os.getenv("USER_ID", "user-001"),
        "eventType":         "BIOMETRIC_REPORT",
        "timestamp":         now.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "deliriumSuspected": delirium_suspected,
        "processedSensorData": {
            "heartRate":     bio["heart_rate"],
            "sleepState":    bio["sleep_state"],
            "activityLevel": bio["activity_level"],
            "steps":         bio.get("steps", 0),
            "bioTimestamp":  bio.get("timestamp", ""),
        },
    }