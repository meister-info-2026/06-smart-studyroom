# 라즈베리파이 5 클라이언트 (pi/)

AI 스마트 학습 좌석 프로젝트의 하드웨어 데몬 및 테스트 스크립트 디렉토리입니다.

## ⚠️ 라즈베리파이 5 (RP1 칩셋) 환경 설정 안내

라즈베리파이 5는 새로운 I/O 컨트롤러인 **RP1 칩셋**이 적용되어 이전 세대의 `RPi.GPIO` 라이브러리가 동작하지 않으며, `gpiozero`와 `lgpio`가 필수입니다.
또한 PyPI에서 `pip install lgpio`를 실행할 경우 C 컴파일 오류가 발생하므로, 반드시 라즈베리파이 OS 기본 **APT 패키지**를 사용하고 가상환경 생성 시 `--system-site-packages` 옵션을 적용합니다.

---

## 🚀 빠른 시작 (Quickstart)

라즈베리파이 터미널에서 아래 명령어를 순서대로 실행하세요:

```bash
cd pi

# 1. 시스템 기본 패키지로 gpiozero 및 lgpio 설치 (컴파일 오류 방지)
sudo apt update
sudo apt install -y python3-gpiozero python3-lgpio

# 2. 시스템 패키지를 재사용하는 가상환경 생성 및 활성화
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 3. 추가 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 파일 복사 및 백엔드 IP 설정
cp .env.example .env
nano .env
# -> BACKEND_URL=http://<학생_PC_IPv4>:8000
# -> DEVICE_API_KEY 확인
```

---

## 🧪 단계별 실행

1. **1단계: 백엔드 연결 확인 (Ping)**
   ```bash
   python 01_ping_backend.py
   ```
2. **2단계: 가상 좌석 데몬 테스트 (Mock 모드)**
   ```bash
   python 02_seat_daemon_mock.py
   ```
3. **3단계: 실기기 제어 데몬 실행 (작성 후)**
   ```bash
   python main.py
   ```
