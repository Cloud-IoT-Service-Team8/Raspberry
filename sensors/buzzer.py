# ============================================================
# sensors/buzzer.py
# 능동형 버저 제어
#
# [연결 핀]
# (+) → GPIO 17 (Pin 11)
# (-) → GND    (Pin 14)
# ============================================================

import time
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

BUZZER_PIN = 17
# 비프 패턴: [(ON초, OFF초), ...]
BUZZER_PATTERN = [(0.4, 0.2), (0.4, 0.2), (0.4, 0.2), (0.8, 0.0)]

try:
    import RPi.GPIO as GPIO
    HW_AVAILABLE = True
except (ImportError, RuntimeError):
    HW_AVAILABLE = False
    logging.warning("[BUZZER] 하드웨어 없음 - 시뮬레이션 모드")


class Buzzer:

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if HW_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
            logger.info("[BUZZER] 초기화 완료 (GPIO %d)", BUZZER_PIN)
        else:
            logger.warning("[BUZZER] 시뮬레이션 모드")

    def alert(self):
        """경고음 재생 (비차단 - 별도 스레드)"""
        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._play, name="buzzer", daemon=True)
        self._thread.start()
        logger.info("[BUZZER] 🔔 경고음 시작")

    def stop(self):
        """경고음 즉시 중지"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._off()

    def cleanup(self):
        self.stop()
        if HW_AVAILABLE:
            GPIO.cleanup(BUZZER_PIN)

    def _play(self):
        for on_sec, off_sec in BUZZER_PATTERN:
            if self._stop_event.is_set():
                break
            self._on()
            time.sleep(on_sec)
            self._off()
            if off_sec > 0:
                time.sleep(off_sec)
        self._off()

    def _on(self):
        if HW_AVAILABLE:
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
        else:
            logger.debug("[BUZZER][SIM] ON")

    def _off(self):
        if HW_AVAILABLE:
            GPIO.output(BUZZER_PIN, GPIO.LOW)
        else:
            logger.debug("[BUZZER][SIM] OFF")