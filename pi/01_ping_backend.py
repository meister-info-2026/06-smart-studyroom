"""
01_ping_backend.py
--------------------------------------------------------------------------------
[라즈베리파이 5 담당자를 위한 1단계 실습: 백엔드 관리실에 첫 인사 건네기]

* 목적: 라즈베리파이와 백엔드 컴퓨터 사이의 네트워크 통신선이 정상적으로 연결되었는지 확인합니다.
* 비유: 관리실(백엔드) 문을 노크하고 "지금 어떤 스마트 부품들이 연결되어 있나요?" 물어봅니다.
* 실행 방법:
    cd pi
    python 01_ping_backend.py
--------------------------------------------------------------------------------
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Windows 터미널(cp949) 이모지 인코딩 오류 방지
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 1. pi/.env 파일에서 백엔드 주소를 읽어옵니다.
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/")
if BACKEND_URL.startswith("http:/") and not BACKEND_URL.startswith("http://"):
    BACKEND_URL = "http://" + BACKEND_URL[6:]
elif BACKEND_URL.startswith("https:/") and not BACKEND_URL.startswith("https://"):
    BACKEND_URL = "https://" + BACKEND_URL[7:]

print("=" * 65)
print("💺 [라즈베리파이 5] AI 스마트 학습 좌석 관리실(백엔드)로 인사를 건넵니다...")
print(f"📡 연결 시도 주소: {BACKEND_URL}/api/devices")
print("=" * 65)

try:
    # 관리실에 GET 요청으로 현재 등록된 좌석 부품 목록을 물어봅니다.
    response = requests.get(f"{BACKEND_URL}/api/devices", timeout=3)

    if response.status_code == 200:
        data = response.json().get("data", [])
        print("\n🎉 [성공 200 OK] 백엔드 관리실과 통신선이 완벽하게 연결되었습니다!")
        print(f"📋 관리실 장부에 등록된 스마트 좌석 부품 개수: {len(data)}개")
        print("\n[현재 등록된 스마트 좌석 부품 목록]")
        for dev in data:
            dev_id = dev.get("id", "unknown")
            name = dev.get("name", "이름 없음")
            kind = dev.get("kind", "알 수 없음")
            print(f"  - ID: {dev_id:<20} | 이름: {name:<25} | 종류: {kind}")
        print("\n✨ 축하합니다! 통신 기초가 확인되었으니 2단계(02_seat_daemon_mock.py)로 넘어가세요!\n")
    else:
        print(f"\n⚠️ [응답 코드 이상] 백엔드가 응답했지만 코드가 다릅니다: {response.status_code}")
        print("응답 본문:", response.text)

except requests.exceptions.ConnectionError:
    print("\n❌ [연결 실패: Connection Error]")
    print("백엔드 관리실 컴퓨터에 연결할 수 없습니다!")
    print("\n💡 [초보자를 위한 3초 해결 팁]")
    print(" 1. 백엔드 담당 친구가 FastAPI 서버(uvicorn)를 실행했는지 확인하세요.")
    print(f" 2. pi/.env 의 BACKEND_URL({BACKEND_URL})에 친구 컴퓨터의 IP가 맞는지 확인하세요.")
    print(" 3. 두 컴퓨터가 동일한 Wi-Fi(공유기)에 연결되어 있는지 확인하세요.")
    print(" 4. 백엔드 PC 방화벽에서 8000번 포트가 열려있는지 확인하세요.\n")
except Exception as e:
    print(f"\n❌ [예상치 못한 오류 발생]: {e}\n")
