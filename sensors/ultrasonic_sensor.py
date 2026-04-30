# ============================================================
# sensors/ultrasonic_sensor.py
# HC-SR04 초음파 센서 제어
#
# [연결 핀]
# VCC  → 5V   (Pin 2)
# GND  → GND  (Pin 9)
# TRIG → GPIO 23 (Pin 16)
# ECHO → GPIO 24 (Pin 18) ※전압분배 필수 (1kΩ + 2kΩ)
#
# [전압분배 회로]
# ECHO(5V) ─[1kΩ]─ A점 ─[2kΩ]─ GND
#                   │
#               GPIO 24
# ============================================================

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TRIG_PIN           = 23
ECHO_PIN           = 24
DOOR_OPEN_CM       = 30.0    # 이 거리 이하면 문 개방으로 판단
TIMEOUT_SEC        = 0.05
SOUND_SPEED        = 34300.0 # cm/s (20°C 기준)

try:
    import RPi.GPIO as GPIO
    HW_AVAILABLE = True
except (ImportError, RuntimeError):
    HW_AVAILABLE = False
    logging.warning("[ULTRASONIC] 하드웨어 없음 - 시뮬레이션 모드")


class UltrasonicSensor:

    def __init__(self):
        if HW_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(ECHO_PIN, GPIO.IN)
            logger.info("[ULTRASONIC] 초기화 완료 (TRIG=%d, ECHO=%d)", TRIG_PIN, ECHO_PIN)
        else:
            logger.warning("[ULTRASONIC] 시뮬레이션 모드")

    def measure_distance_cm(self) -> Optional[float]:
        """거리 측정 (cm). 실패 시 None 반환"""
        if not HW_AVAILABLE:
            return None
        try:
            return self._measure()
        except Exception as e:
            logger.error("[ULTRASONIC] 측정 오류: %s", e)
            return None

    def is_door_open(self) -> bool:
        """DOOR_OPEN_CM 이하면 문 개방으로 판단"""
        dist = self.measure_distance_cm()
        if dist is None:
            return False
        result = dist <= DOOR_OPEN_CM
        logger.debug("[ULTRASONIC] %.1f cm → 문 %s", dist, "열림" if result else "닫힘")
        return result

    def cleanup(self):
        if HW_AVAILABLE:
            GPIO.cleanup()

    def _measure(self) -> Optional[float]:
        # TRIG 10μs 펄스
        GPIO.output(TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIG_PIN, GPIO.LOW)

        # ECHO 시작 대기
        start = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.LOW:
            if time.time() - start > TIMEOUT_SEC:
                return None
        pulse_start = time.time()

        # ECHO 종료 대기
        while GPIO.input(ECHO_PIN) == GPIO.HIGH:
            if time.time() - pulse_start > TIMEOUT_SEC:
                return None
        pulse_end = time.time()

        return round((pulse_end - pulse_start) * SOUND_SPEED / 2.0, 1)