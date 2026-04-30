# ============================================================
# sensors/rfid_sensor.py
# MFRC522 RFID 센서 제어
#
# [연결 핀]
# 3.3V  → Pin 1
# GND   → Pin 6
# RST   → GPIO 25 (Pin 22)
# SDA   → GPIO 8  (Pin 24) SPI CE0
# SCK   → GPIO 11 (Pin 23) SPI CLK
# MOSI  → GPIO 10 (Pin 19) SPI MOSI
# MISO  → GPIO 9  (Pin 21) SPI MISO
# ============================================================

import os
import time
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# 인가된 RFID 태그 ID 목록 (실제 태그 읽히면 로그에 ID 출력됨 → 그 값으로 교체)
AUTHORIZED_TAGS     = [int(x) for x in os.getenv("RFID_AUTHORIZED_TAGS", "").split(",") if x]
RFID_VALID_SEC      = 5.0   # 태그 인식 후 유효 시간 (초)

try:
    from mfrc522 import SimpleMFRC522
    import RPi.GPIO as GPIO
    HW_AVAILABLE = True
except (ImportError, RuntimeError):
    HW_AVAILABLE = False
    logger.warning("[RFID] 하드웨어 없음 - 시뮬레이션 모드")


class RFIDSensor:

    def __init__(self):
        self._last_tag_id:   Optional[int] = None
        self._last_detected: float         = 0.0
        self._lock       = threading.Lock()
        self._stop_event = threading.Event()
        self._thread:    Optional[threading.Thread] = None

        if HW_AVAILABLE:
            self._reader = SimpleMFRC522()
            logger.info("[RFID] 초기화 완료")
        else:
            self._reader = None

    def start(self):
        """배경 스레드 시작 - 프로그램 시작 시 1회 호출"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="rfid", daemon=True)
        self._thread.start()
        logger.info("[RFID] 읽기 스레드 시작")

    def stop(self):
        """배경 스레드 종료"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        if HW_AVAILABLE:
            GPIO.cleanup()
        logger.info("[RFID] 정지")

    def is_authorized_recently(self) -> bool:
        """최근 RFID_VALID_SEC 이내에 인가된 태그 인식 여부"""
        with self._lock:
            if self._last_tag_id is None:
                return False
            elapsed  = time.time() - self._last_detected
            is_auth  = self._last_tag_id in AUTHORIZED_TAGS
            is_recent = elapsed <= RFID_VALID_SEC
            return is_auth and is_recent

    def inject_for_test(self, tag_id: int):
        """테스트용 태그 주입"""
        with self._lock:
            self._last_tag_id   = tag_id
            self._last_detected = time.time()

    def _loop(self):
        while not self._stop_event.is_set():
            if not HW_AVAILABLE:
                time.sleep(0.5)
                continue
            try:
                tag_id, _ = self._reader.read()
                with self._lock:
                    self._last_tag_id   = tag_id
                    self._last_detected = time.time()
                if tag_id in AUTHORIZED_TAGS:
                    logger.info("[RFID] ✅ 인가 태그: %d", tag_id)
                else:
                    logger.warning("[RFID] ⚠️ 미인가 태그: %d", tag_id)
                time.sleep(1.0)
            except Exception as e:
                logger.error("[RFID] 읽기 오류: %s", e)
                time.sleep(1.0)