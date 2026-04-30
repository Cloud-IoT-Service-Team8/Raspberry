# ============================================================
# api/fitbit_client.py
# Google Fitness API 폴링 - 심박수 / 수면 / 활동량
# ============================================================

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CLIENT_ID     = os.getenv("FITBIT_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("FITBIT_REFRESH_TOKEN", "")


def get_dynamic_source(token: str, data_type_name: str) -> str:
    """iOS/Apple Health 데이터 소스를 우선 탐색한다."""
    url = "https://www.googleapis.com/fitness/v1/users/me/dataSources"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code != 200:
        logger.error("[FITBIT] 데이터 소스 조회 실패 %d: %s", resp.status_code, resp.text)
        return ""

    sources = resp.json().get("dataSource", [])

    for src in sources:
        stream_id = src.get("dataStreamId", "")
        if src.get("dataType", {}).get("name") == data_type_name:
            if "apple.health" in stream_id or "ios" in stream_id:
                return stream_id

    for src in sources:
        if src.get("dataType", {}).get("name") == data_type_name:
            return src.get("dataStreamId", "")

    return ""


def get_access_token():
    """refresh_token으로 access_token 갱신"""
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }, timeout=10)

    if resp.status_code == 200:
        token = resp.json().get("access_token")
        logger.debug("[FITBIT] 토큰 갱신 성공")
        return token
    else:
        logger.error("[FITBIT] 토큰 갱신 실패 %d: %s", resp.status_code, resp.text)
        return None


def fetch_heart_rate(token):
    """최근 5분 평균 심박수 반환 (bpm)"""
    now_ns   = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (5 * 60 * 1_000_000_000)
    src = get_dynamic_source(token, "com.google.heart_rate.bpm")
    if not src:
        logger.warning("[FITBIT] 심박수 데이터 소스를 찾을 수 없음")
        return None

    url = (
        f"https://www.googleapis.com/fitness/v1/users/me"
        f"/dataSources/{src}/datasets/{start_ns}-{now_ns}"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code == 200:
        points = resp.json().get("point", [])
        if points:
            hr = points[-1]["value"][0]["fpVal"]
            logger.info("[FITBIT] 심박수: %.1f bpm", hr)
            return round(hr, 1)
        logger.warning("[FITBIT] 심박수 데이터 없음")
        return None
    else:
        logger.error("[FITBIT] 심박수 요청 실패 %d: %s", resp.status_code, resp.text)
        return None


def fetch_sleep(token):
    """
    최근 24시간 수면 데이터 반환
    Returns: {"sleep_state": str, "wake_ratio": float}
    """
    now_ns   = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (24 * 60 * 60 * 1_000_000_000)
    src = get_dynamic_source(token, "com.google.sleep.segment")
    if not src:
        logger.warning("[FITBIT] 수면 데이터 소스를 찾을 수 없음")
        return None

    url = (
        f"https://www.googleapis.com/fitness/v1/users/me"
        f"/dataSources/{src}/datasets/{start_ns}-{now_ns}"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code == 200:
        points = resp.json().get("point", [])
        if not points:
            logger.info("[FITBIT] 수면 데이터 없음 - AWAKE로 처리")
            return {"sleep_state": "AWAKE", "wake_ratio": 0.0}

        # Google Fit 수면 타입 매핑
        # 1=awake, 2=sleep, 3=out-of-bed, 4=light, 5=deep, 6=rem
        type_map = {1: "AWAKE", 2: "LIGHT", 3: "AWAKE", 4: "LIGHT", 5: "DEEP", 6: "REM"}
        total      = len(points)
        wake_count = sum(1 for p in points if p["value"][0].get("intVal", 0) in [1, 3])
        latest     = points[-1]["value"][0].get("intVal", 1)
        sleep_state = type_map.get(latest, "UNKNOWN")
        wake_ratio  = round(wake_count / total, 3) if total > 0 else 0.0

        if sleep_state == "UNKNOWN":
            logger.warning("[FITBIT] 알 수 없는 수면 상태 코드: %s", latest)

        logger.info("[FITBIT] 수면: %s (각성 %.0f%%)", sleep_state, wake_ratio * 100)
        return {"sleep_state": sleep_state, "wake_ratio": wake_ratio}
    else:
        logger.error("[FITBIT] 수면 요청 실패 %d", resp.status_code)
        return None


def fetch_activity(token):
    """
    오늘 활동량 반환
    Returns: {"activity_level": int (0~100), "steps": int}
    """
    now_ns   = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (24 * 60 * 60 * 1_000_000_000)
    src = get_dynamic_source(token, "com.google.step_count.delta")
    if not src:
        logger.warning("[FITBIT] 활동량 데이터 소스를 찾을 수 없음")
        return None

    url = (
        f"https://www.googleapis.com/fitness/v1/users/me"
        f"/dataSources/{src}/datasets/{start_ns}-{now_ns}"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code == 200:
        points = resp.json().get("point", [])
        steps  = sum(p["value"][0].get("intVal", 0) for p in points)
        activity_level = round(min(steps / 10000.0, 1.0) * 100)
        logger.info("[FITBIT] 걸음 수: %d (activity: %d)", steps, activity_level)
        return {"activity_level": activity_level, "steps": steps}
    else:
        logger.error("[FITBIT] 활동량 요청 실패 %d", resp.status_code)
        return None


def fetch_all():
    """
    토큰 갱신 후 전체 생체 데이터 수집.
    Returns: dict 또는 None
    """
    token = get_access_token()
    if not token:
        return None

    hr       = fetch_heart_rate(token)
    sleep    = fetch_sleep(token)
    activity = fetch_activity(token)

    if hr is None or sleep is None or activity is None:
        logger.warning("[FITBIT] 일부 데이터 수집 실패")
        return None

    return {
        "user_id":        os.getenv("USER_ID", "user-001"),
        "device_id":      os.getenv("DEVICE_ID", "rpi-001"),
        "timestamp":      datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "heart_rate":     hr,
        "sleep_state":    sleep["sleep_state"],
        "wake_ratio":     sleep["wake_ratio"],
        "activity_level": activity["activity_level"],
        "steps":          activity["steps"],
    }
