#!/usr/bin/env python3
# ============================================================
# test/test_fitbit_api.py
# Google Fitness API 연결 테스트 (iOS 동적 탐색 + 최근 5분 고정)
# 실행: python3 test/test_fitbit_api.py (RaspberryPi/ 루트에서)
# ============================================================

import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("FITBIT_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("FITBIT_REFRESH_TOKEN", "")


def ok(msg):   print(f"  ✅ {msg}")
def fail(msg): print(f"  ❌ {msg}")
def info(msg): print(f"  ℹ️  {msg}")
def section(title): print(f"\n{'='*50}\n  {title}\n{'='*50}")


# ============================================================
# 아이폰(iOS) 전용 동적 데이터 소스 탐색 함수
# ============================================================
def get_dynamic_source(token: str, data_type_name: str) -> str:
    url = "https://www.googleapis.com/fitness/v1/users/me/dataSources"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    
    if resp.status_code == 200:
        sources = resp.json().get("dataSource", [])
        
        for src in sources:
            stream_id = src.get("dataStreamId", "")
            if src.get("dataType", {}).get("name") == data_type_name:
                if "apple.health" in stream_id or "ios" in stream_id:
                    return stream_id
                    
        for src in sources:
            if src.get("dataType", {}).get("name") == data_type_name:
                return src.get("dataStreamId")
                
    return ""

# ============================================================
# 1. .env 로드 확인
# ============================================================

def test_env() -> bool:
    section("1. .env 로드 확인")
    all_ok = True
    for key, val in [
        ("FITBIT_CLIENT_ID",     CLIENT_ID),
        ("FITBIT_CLIENT_SECRET", CLIENT_SECRET),
        ("FITBIT_REFRESH_TOKEN", REFRESH_TOKEN),
    ]:
        if val:
            ok(f"{key} 로드됨 (...{val[-6:]})")
        else:
            fail(f"{key} 비어 있음 → .env 확인 필요")
            all_ok = False
    return all_ok


# ============================================================
# 2. 토큰 갱신
# ============================================================

def refresh_token() -> str | None:
    section("2. Google OAuth 토큰 갱신")
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }, timeout=10)

    if resp.status_code == 200:
        token = resp.json().get("access_token")
        ok(f"토큰 갱신 성공 (...{token[-10:]})")
        return token
    else:
        fail(f"토큰 갱신 실패 {resp.status_code}: {resp.text}")
        return None


# ============================================================
# 3. 심박수 수신
# ============================================================

def test_heart_rate(token: str):
    section("3. 심박수 수신 (최근 5분)")
    now_ns   = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (5 * 60 * 1_000_000_000) # 원본대로 5분 복구
    
    src = get_dynamic_source(token, "com.google.heart_rate.bpm")
    
    if not src:
        fail("심박수 데이터 소스를 찾을 수 없습니다.")
        return
        
    info(f"사용 중인 데이터 소스: {src}")
    
    url = (
        f"https://www.googleapis.com/fitness/v1/users/me"
        f"/dataSources/{src}/datasets/{start_ns}-{now_ns}"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code == 200:
        points = resp.json().get("point", [])
        if points:
            hr = points[-1]["value"][0]["fpVal"]
            ok(f"심박수: {hr:.1f} bpm ({len(points)}개 포인트)")
        else:
            fail("데이터 없음 - 최근 5분 내에 측정/동기화된 심박수가 없습니다.")
    else:
        fail(f"요청 실패 {resp.status_code}: {resp.text}")


# ============================================================
# 4. 수면 데이터 수신 (수면은 24시간 유지 - 어젯밤 기록이므로)
# ============================================================

def test_sleep(token: str):
    section("4. 수면 데이터 수신 (최근 24시간)")
    now_ns   = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (24 * 60 * 60 * 1_000_000_000) 
    
    src = get_dynamic_source(token, "com.google.sleep.segment")
    
    if not src:
        fail("수면 데이터 소스를 찾을 수 없습니다.")
        return

    info(f"사용 중인 데이터 소스: {src}")
        
    url = (
        f"https://www.googleapis.com/fitness/v1/users/me"
        f"/dataSources/{src}/datasets/{start_ns}-{now_ns}"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code == 200:
        points = resp.json().get("point", [])
        if points:
            type_map = {1: "AWAKE", 3: "AWAKE", 4: "LIGHT", 5: "DEEP", 6: "REM"}
            latest   = points[-1]["value"][0].get("intVal", 1)
            ok(f"수면 데이터: {len(points)}개 포인트 | 최근 상태: {type_map.get(latest, 'UNKNOWN')}")
        else:
            fail("수면 데이터 없음 (동기화 전일 수 있음)")
    else:
        fail(f"요청 실패 {resp.status_code}: {resp.text}")


# ============================================================
# 5. 활동량 (걸음 수) 수신
# ============================================================

def test_activity(token: str):
    section("5. 활동량 수신 (최근 24시간)")
    now_ns   = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (24 * 60 * 60 * 1_000_000_000)
    
    src = get_dynamic_source(token, "com.google.step_count.delta")
    
    if not src:
        fail("걸음 수 데이터 소스를 찾을 수 없습니다.")
        return

    info(f"사용 중인 데이터 소스: {src}")

    url = (
        f"https://www.googleapis.com/fitness/v1/users/me"
        f"/dataSources/{src}/datasets/{start_ns}-{now_ns}"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)

    if resp.status_code == 200:
        points = resp.json().get("point", [])
        steps  = sum(p["value"][0].get("intVal", 0) for p in points)
        activity_level = round(min(steps / 10000.0, 1.0) * 100)
        ok(f"걸음 수: {steps}보 | activity_level: {activity_level}")
    else:
        fail(f"요청 실패 {resp.status_code}: {resp.text}")


# ============================================================
# 메인
# ============================================================

if __name__ == "__main__":
    print(f"\n🔍 Google Fitness API 테스트 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not test_env():
        print("\n⛔ .env 확인 후 다시 실행하세요.")
        exit(1)

    token = refresh_token()
    if not token:
        print("\n⛔ 토큰 갱신 실패.")
        exit(1)

    test_heart_rate(token)
    test_sleep(token)
    test_activity(token)

    print(f"\n{'='*50}\n  테스트 완료\n{'='*50}\n")