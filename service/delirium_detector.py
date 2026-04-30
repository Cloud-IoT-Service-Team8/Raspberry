# ============================================================
# logic/delirium_detector.py
# 섬망 판단 로직 R-02 ~ R-05
# ============================================================

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

HEART_RATE_HIGH        = 100
HEART_RATE_LOW         = 50
ACTIVITY_THRESHOLD     = 60
DELIRIUM_VALID_SEC     = 1800   # 30분


@dataclass
class SensorState:
    door_open:       bool
    rfid_authorized: bool


@dataclass
class DeliriumState:
    abnormal_heart_rate:      bool  = False
    abnormal_sleep:           bool  = False
    abnormal_activity:        bool  = False
    delirium_suspected:       bool  = False
    suspected_since:          float = 0.0
    abnormal_exit:            bool  = False
    delirium_event_triggered: bool  = False

    def is_valid(self):
        if not self.delirium_suspected:
            return False
        return (time.time() - self.suspected_since) <= DELIRIUM_VALID_SEC


class DeliriumDetector:

    def evaluate(self, bio: dict, sensor: SensorState, prev: Optional[DeliriumState] = None) -> DeliriumState:
        state = DeliriumState()
        sleep_state = str(bio.get("sleep_state", "UNKNOWN")).upper()

        # R-02: 생체 이상 판단
        state.abnormal_heart_rate = (
            bio["heart_rate"] > HEART_RATE_HIGH or
            bio["heart_rate"] < HEART_RATE_LOW
        )
        state.abnormal_sleep    = sleep_state in {"AWAKE", "UNKNOWN"}
        state.abnormal_activity = (bio["activity_level"] > ACTIVITY_THRESHOLD)
        state.delirium_suspected = (
            state.abnormal_heart_rate or
            state.abnormal_sleep or
            state.abnormal_activity
        )

        if state.delirium_suspected:
            state.suspected_since = prev.suspected_since if (prev and prev.is_valid()) else time.time()
            logger.warning(
                "[DETECTOR] ⚠️ 섬망 의심 | HR이상=%s | 수면=%s | 활동이상=%s",
                state.abnormal_heart_rate, sleep_state, state.abnormal_activity
            )

        # R-03/R-04: 출입 이상 판단
        state.abnormal_exit = sensor.door_open and not sensor.rfid_authorized
        if sensor.door_open:
            logger.info("[DETECTOR] 문 개방 | RFID: %s",
                        "인증" if sensor.rfid_authorized else "미인증")

        # R-05: 최종 이벤트
        state.delirium_event_triggered = state.is_valid() and state.abnormal_exit
        if state.delirium_event_triggered:
            logger.critical("[DETECTOR] 섬망 이벤트 발생!")

        return state
