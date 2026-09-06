"""
02_seat_daemon_mock.py
--------------------------------------------------------------------------------
[라즈베리파이 5 담당자를 위한 2단계 실습: 스마트 학습 좌석 가상 제어 데몬 (Mock 모드)]

* 목적:
    - 2~3초마다 백엔드 관리실에 "지금 의자나 조명에 지시할 사항이 있나요?" 확인(GET desired-state)합니다.
    - 실제 모터나 전선을 꽂지 않고도 print() 출력으로 가상 하드웨어 동작을 눈으로 검증합니다.
    - 상태가 변경되면 관리실에 "지시대로 동작을 완료했습니다!" 하고 보고(POST state)합니다.
    - 프론트엔드 웹 대시보드에서 스위치나 버튼을 조작했을 때 이 데몬이 감지하는 모습을 확인합니다.

* 실행 방법:
    cd pi
    python 02_seat_daemon_mock.py
--------------------------------------------------------------------------------
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# Windows 터미널(cp949) 이모지 인코딩 오류 방지
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 1. 환경변수 불러오기
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "STUDY_ROOM_2026_09_05_v1_0_0")

HEADERS = {
    "X-Device-Api-Key": DEVICE_API_KEY,
    "Content-Type": "application/json",
}

# 우리가 감시하고 제어할 스마트 좌석 액추에이터 목록
ACTUATORS = [
    {"id": "rgb_led",           "name": "RGB LED 바(스탠드 조명)",     "emoji": "💡", "kind": "led"},
    {"id": "vibration_motor_a", "name": "소형 진동 모터 A(등받이 자세)", "emoji": "📳", "kind": "vibrator"},
    {"id": "vibration_motor_b", "name": "소형 진동 모터 B(방석 졸음)",   "emoji": "💤", "kind": "vibrator"},
    {"id": "relay_power",       "name": "릴레이/MOSFET 전원 모듈",      "emoji": "⚡", "kind": "relay"},
]

# 현재 라즈베리파이(가상 좌석)가 기억하고 있는 각 부품의 실제 상태 (초기값)
my_current_states = {
    "rgb_led": "off",
    "vibration_motor_a": "off",
    "vibration_motor_b": "off",
    "relay_power": "off",
}

print("=" * 75)
print("💺 [라즈베리파이 5] AI 스마트 학습 좌석 제어 데몬 가동 (Mock 시뮬레이터)")
print(f"📡 관리실(백엔드) 주소: {BACKEND_URL}")
print(f"🔑 출입증 API 키: {DEVICE_API_KEY[:10]}********")
print(f"🎯 제어 대상 부품: {[a['id'] for a in ACTUATORS]}")
print("⏱️  폴링 주기: 2.5초 (종료하려면 터미널에서 Ctrl + C 를 누르세요)")
print("=" * 75)


def simulate_hardware_action(device_id: str, new_state: str, new_value: any):
    """실제 하드웨어가 연결되기 전, 디버깅용 print로 액추에이터의 물리적 동작을 시뮬레이션합니다."""
    if device_id == "rgb_led":
        if new_state in ("on", "active"):
            brightness = 80
            if isinstance(new_value, dict) and "brightness" in new_value:
                brightness = new_value["brightness"]
            print(f"      ✨ [LED 점등] 스탠드 조명이 켜졌습니다! (색상: 주백색 4500K, 밝기: {brightness}%)")
        else:
            print("      🌑 [LED 소등] 스탠드 조명이 꺼졌습니다. (절전 모드)")

    elif device_id == "vibration_motor_a":
        if new_state in ("on", "active", "warning"):
            print("      ⚠️ [등받이 진동 발생!!] 드르륵~ 드르륵~ (거북목/고개 숙임 자세 불균형 교정 알림!)")
        else:
            print("      ✨ [등받이 진동 정지] 올바른 자세 유지 중. 진동을 끕니다.")

    elif device_id == "vibration_motor_b":
        if new_state in ("on", "active", "alert"):
            print("      🚨 [방석 진동 쿵쿵쿵!!] 펄스 진동 발생! (눈 감김 지속 감지 - 졸음 깨우기 알림!)")
        else:
            print("      ✨ [방석 진동 정지] 학습 집중 상태 복귀. 진동을 끕니다.")

    elif device_id == "relay_power":
        if new_state in ("on", "active"):
            print("      ⚡ [릴레이 ON] 찰칵(Click)! 좌석 메인 전원이 인가되었습니다.")
        else:
            print("      🔌 [릴레이 OFF] 찰칵(Click)! 좌석 대기 전원을 차단합니다.")


def poll_and_execute(actuator):
    """관리실의 목표 상태를 확인하고, 변경이 있으면 가상 하드웨어 동작 후 보고합니다."""
    device_id = actuator["id"]
    name = actuator["name"]
    emoji = actuator["emoji"]

    desired_url = f"{BACKEND_URL}/api/v1/devices/{device_id}/desired-state"

    try:
        # 1. 관리실 목표 상태 확인 (GET desired-state)
        res = requests.get(desired_url, headers=HEADERS, timeout=3)
        if res.status_code == 401:
            print(f"❌ [401 권한 오류] DEVICE_API_KEY 가 백엔드와 다릅니다! pi/.env 를 확인하세요.")
            return
        elif res.status_code == 404:
            print(f"❌ [404 미등록] '{device_id}' 디바이스가 백엔드 DB에 등록되어 있지 않습니다.")
            return
        elif res.status_code != 200:
            print(f"⚠️ [응답 이상 {res.status_code}] {device_id} 조회 실패: {res.text}")
            return

        body = res.json().get("data", {})
        desired_state = body.get("desired_state")
        desired_value = body.get("desired_value")

        # 만약 DB에 desired_state 가 설정되어 있지 않으면 기본값 off 로 간주
        if not desired_state:
            desired_state = "off"

        # 2. 상태 변경 여부 확인 (기존 실제 상태와 다른가?)
        current_local = my_current_states.get(device_id, "off")

        if desired_state != current_local:
            print(f"\n🔔 {emoji} [{name}] 상태 변경 지시 감지!")
            print(f"   - 관리실 지시: [{current_local}] ➔ [{desired_state}] (부가값: {desired_value})")

            # 3. 가상 하드웨어 동작 실행 (디버깅용 시뮬레이션 print)
            simulate_hardware_action(device_id, desired_state, desired_value)

            # 4. 관리실에 완료 보고 (POST state)
            state_url = f"{BACKEND_URL}/api/v1/devices/{device_id}/state"
            payload = {
                "current_state": desired_state,
                "current_value": desired_value
            }
            report_res = requests.post(state_url, json=payload, headers=HEADERS, timeout=3)

            if report_res.status_code == 200:
                print(f"   ✅ [보고 완료] 백엔드에 '{desired_state}' 반영 완료를 알렸습니다! (대시보드 동기화 됨)")
                my_current_states[device_id] = desired_state
            else:
                print(f"   ⚠️ [보고 실패 {report_res.status_code}] {report_res.text}")

    except requests.exceptions.ConnectionError:
        print(f"⚠️ [연결 끊김] 백엔드 서버({BACKEND_URL})에 연결할 수 없습니다. 서버가 켜져 있는지 확인하세요.")
    except Exception as e:
        print(f"❌ [{device_id}] 처리 중 오류: {e}")


def main():
    try:
        iteration = 1
        while True:
            # 2.5초마다 모든 액추에이터 순차 폴링
            for actuator in ACTUATORS:
                poll_and_execute(actuator)

            # 콘솔에 생존 하트비트 점 찍기 (너무 시끄럽지 않게 유지)
            sys.stdout.write(f"\r⏳ [스마트 좌석 데몬] 백엔드 신호 대기 중... (폴링 횟수: {iteration}회) ")
            sys.stdout.flush()

            iteration += 1
            time.sleep(2.5)

    except KeyboardInterrupt:
        print("\n\n🛑 [데몬 종료] 사용자가 프로그램을 종료했습니다. 안녕히 가세요!")


if __name__ == "__main__":
    main()
