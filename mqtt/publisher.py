# ============================================================
# mqtt/publisher.py
# MQTT 브로커 연결 및 메시지 전송
# 토픽 하나로 통일 - 섬망이든 아니든 같은 토픽으로 전송
# ============================================================

import os
import json
import logging
import time
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "8883"))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "healthcare/user-001/event")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", os.getenv("USERNAME", ""))
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", os.getenv("PASSWORD", ""))

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    logger.warning("[MQTT] paho-mqtt 미설치 - 시뮬레이션 모드")


class MQTTPublisher:

    def __init__(self):
        self._connected = False
        self._client    = None

        if PAHO_AVAILABLE:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self._client.on_connect    = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            if MQTT_USERNAME or MQTT_PASSWORD:
                self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            self._client.tls_set()
            logger.info("[MQTT] 초기화 | %s:%d | 토픽: %s", MQTT_BROKER, MQTT_PORT, MQTT_TOPIC)
        else:
            logger.warning("[MQTT] 시뮬레이션 모드")

    def connect(self) -> bool:
        if not PAHO_AVAILABLE:
            self._connected = True
            return True
        if not MQTT_BROKER:
            logger.error("[MQTT] MQTT_BROKER 미설정 → .env 확인")
            return False
        try:
            self._client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self._client.loop_start()

            start = time.time()
            while not self._connected and (time.time() - start) < 5:
                time.sleep(0.1)

            return self._connected
        except Exception as e:
            logger.error("[MQTT] 연결 실패: %s", e)
            return False

    def publish(self, payload: dict) -> bool:
        """항상 MQTT_TOPIC 하나로 전송"""
        if not PAHO_AVAILABLE:
            logger.info("[MQTT][SIM] → %s | %s", MQTT_TOPIC, json.dumps(payload, ensure_ascii=False))
            return True

        if not self._connected:
            logger.warning("[MQTT] 미연결 → 재연결 시도")
            if not self.connect():
                return False

        try:
            result = self._client.publish(
                MQTT_TOPIC,
                json.dumps(payload, ensure_ascii=False),
                qos=1
            )
            result.wait_for_publish(timeout=5.0)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("[MQTT] 전송 완료 → %s", MQTT_TOPIC)
                return True

            logger.error("[MQTT] 전송 실패 rc=%s", result.rc)
            return False
        except Exception as e:
            logger.error("[MQTT] 전송 실패: %s", e)
            return False

    def disconnect(self):
        if PAHO_AVAILABLE and self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False
        logger.info("[MQTT] 연결 해제")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self._connected = (rc == 0)
        if rc == 0:
            logger.info("[MQTT] 브로커 연결 성공")
        else:
            logger.error("[MQTT] 연결 실패 rc=%s", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning("[MQTT] 연결 끊김 rc=%s", rc)
