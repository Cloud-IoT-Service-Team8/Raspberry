#!/usr/bin/env python3
# ============================================================
# main.py
#
# 흐름: 5분마다
#   1. Fitbit API 폴링 → 생체 데이터
#   2. 초음파 센서 → 거리값
#   3. RFID 인증 여부
#   4. 섬망 판단
#   5. 버저 (섬망 이벤트 시만)
#   6. MQTT 전송 (섬망이든 아니든 무조건)
# ============================================================

import os
import time
import signal
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main")

from api.fitbit_client        import fetch_all
from mqtt.publisher           import MQTTPublisher
from mqtt.model               import build_message
from service.delirium_detector import DeliriumDetector, SensorState

try:
    from sensors.rfid_sensor       import RFIDSensor
    from sensors.ultrasonic_sensor import UltrasonicSensor
    from sensors.buzzer            import Buzzer
    SENSORS_AVAILABLE = True
except Exception:
    SENSORS_AVAILABLE = False
    logger.warning("센서 모듈 없음 - 시뮬레이션 모드")

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))  # 5분

_shutdown = False

def _signal_handler(sig, frame):
    global _shutdown
    logger.info("종료 신호 수신")
    _shutdown = True

signal.signal(signal.SIGINT,  _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def main():
    logger.info("=" * 55)
    logger.info("섬망 모니터링 시스템 시작 | 폴링 주기: %d초", POLL_INTERVAL)
    logger.info("=" * 55)

    publisher = MQTTPublisher()
    detector  = DeliriumDetector()

    if SENSORS_AVAILABLE:
        rfid       = RFIDSensor(); rfid.start()
        ultrasonic = UltrasonicSensor()
        buzzer     = Buzzer()
    else:
        rfid = ultrasonic = buzzer = None

    publisher.connect()

    last_poll = 0.0

    logger.info("메인 루프 시작")

    while not _shutdown:
        loop_start = time.time()

        # 5분 안 됐으면 대기
        if (loop_start - last_poll) < POLL_INTERVAL:
            time.sleep(1.0)
            continue

        last_poll = loop_start
        logger.info("[LOOP] ── 데이터 수집 시작 ──")

        # ── 1. Fitbit API 폴링 ───────────────────────────────
        bio = fetch_all()
        if bio is None:
            logger.warning("[LOOP] Fitbit 수집 실패 - 이번 주기 스킵")
            continue

        logger.info("[BIO] HR=%.1f | sleep=%s | activity=%.2f | steps=%d",
                    bio["heart_rate"], bio["sleep_state"],
                    bio["activity_level"], bio["steps"])

        # ── 2. 센서 읽기 ─────────────────────────────────────
        if SENSORS_AVAILABLE:
            distance  = ultrasonic.measure_distance_cm() or 999.0
            door_open = distance <= 30.0
            rfid_auth = rfid.is_authorized_recently()
        else:
            distance  = 999.0
            door_open = False
            rfid_auth = True

        logger.info("[SENSOR] 거리=%.1fcm | 문=%s | RFID=%s",
                    distance,
                    "열림" if door_open else "닫힘",
                    "✅" if rfid_auth else "❌")

        # ── 3. 섬망 판단 ─────────────────────────────────────
        sensor = SensorState(door_open=door_open, rfid_authorized=rfid_auth)
        state  = detector.evaluate(bio, sensor)

        # ── 4. 버저 (섬망 이벤트 발생 시만) ──────────────────
        buzzer_activated = False
        if state.delirium_event_triggered and SENSORS_AVAILABLE:
            buzzer.alert()
            buzzer_activated = True
            logger.critical("섬망 이벤트 발생!")

        # ── 5. MQTT 전송 ─────────────────────────────
        message = build_message(
            bio                = bio,
            door_distance_cm   = distance,
            delirium_suspected = state.delirium_suspected,
            abnormal_exit      = state.abnormal_exit,
            door_open          = door_open,
            rfid_detected      = rfid_auth,
            buzzer_activated   = buzzer_activated,
        )
        ok = publisher.publish(message)
        logger.info("MQTT 전송: %s | ID: %s | severity: %s",
                    "정상 전송" if ok else "전송 실패",
                    message["eventId"],
                    message["severity"])

    # ── 종료 ─────────────────────────────────────────────────
    logger.info("시스템 종료 중...")
    if SENSORS_AVAILABLE:
        rfid.stop()
        buzzer.cleanup()
        ultrasonic.cleanup()
    publisher.disconnect()
    logger.info("정상 종료")


if __name__ == "__main__":
    main()