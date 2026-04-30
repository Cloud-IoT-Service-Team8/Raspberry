import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER", "")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "healthcare/user-001/event")
USER_ID     = os.getenv("USER_ID", "user-001")
DEVICE_ID   = os.getenv("DEVICE_ID", "rpi-001")
USERNAME = os.getenv("USERNAME", "Cloud-IoT-Service-Team8")
PASSWORD = os.getenv("PASSWORD", "Password1234!")

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

MOCK_PAYLOAD = {
    "eventId":           "evt-20260429-0001",
    "deviceId":          DEVICE_ID,
    "userId":            USER_ID,
    "eventType":         "DELIRIUM_EXIT_RISK",
    "severity":          "HIGH",
    "timestamp":         "2026-04-29T14:30:00+09:00",
    "deliriumSuspected": True,
    "abnormalExit":      True,
    "doorOpen":          True,
    "rfidDetected":      False,
    "buzzerActivated":   True,
    "processedSensorData": {
        "heartRate":      112,
        "sleepState":     "AWAKE",
        "activityLevel":  78,
        "doorDistanceCm": 18.3
    }
}

def ok(msg):    print(f"  ✅ {msg}")
def fail(msg):  print(f"  ❌ {msg}")
def info(msg):  print(f"  ℹ️  {msg}")
def section(t): print(f"\n{'='*50}\n  {t}\n{'='*50}")

def test_env():
    section("1. .env 확인")
    all_ok = True
    for key, val in [
        ("MQTT_BROKER", MQTT_BROKER),
        ("MQTT_PORT",   str(MQTT_PORT)),
        ("MQTT_TOPIC",  MQTT_TOPIC),
    ]:
        if val:
            ok(f"{key} = {val}")
        else:
            fail(f"{key} 비어 있음 → .env 확인 필요")
            all_ok = False
    return all_ok


def test_mqtt():
    section("2. MQTT 브로커 연결")

    if not PAHO_AVAILABLE:
        fail("paho-mqtt 미설치 → pip3 install paho-mqtt")
        return False

    connected = False

    def on_connect(client, userdata, flags, rc, properties=None):
        nonlocal connected
        if rc == 0:
            connected = True
            ok(f"브로커 연결 성공 ({MQTT_BROKER}:{MQTT_PORT})")
        else:
            fail(f"연결 실패 rc={rc}")

    def on_publish(client, userdata, mid):
        ok(f"전송 확인 (mid={mid})")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set()

# client.connect("ce20fda0670040e883fa93e398da046d.s1.eu.hivemq.cloud", 8883, keepalive=60)
# client.loop_forever()

    try:
        info(f"연결 시도 → {MQTT_BROKER}:{MQTT_PORT}")
        client.connect("ce20fda0670040e883fa93e398da046d.s1.eu.hivemq.cloud", 8883, keepalive=60)
        client.loop_start()

        start = time.time()
        while not connected and (time.time() - start) < 5:
            time.sleep(0.1)

        if not connected:
            fail("연결 타임아웃 (5초)")
            return False

    except Exception as e:
        fail(f"연결 오류: {e}")
        return False

    section("3. Mock 데이터 전송")
    payload_str = json.dumps(MOCK_PAYLOAD, ensure_ascii=False, indent=2)
    info(f"토픽: {MQTT_TOPIC}")
    info(f"payload:\n{payload_str}")

    try:
        result = client.publish(MQTT_TOPIC, payload_str, qos=1)
        result.wait_for_publish(timeout=5.0)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            ok("전송 성공!")
        else:
            fail(f"전송 실패 rc={result.rc}")
            return False

    except Exception as e:
        fail(f"전송 오류: {e}")
        return False

    finally:
        time.sleep(0.5)
        client.loop_stop()
        client.disconnect()

    return True


if __name__ == "__main__":
    print("\n🔍 MQTT 통신 테스트")

    if not test_env():
        print("\n⛔ .env 설정 확인 후 다시 실행하세요.")
        exit(1)

    success = test_mqtt()

    print(f"\n{'='*50}")
    print(f"  결과: {'✅ 성공' if success else '❌ 실패'}")
    print(f"{'='*50}\n")
