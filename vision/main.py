import logging
import os
import sys
import time
from typing import Optional

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from ultralytics import YOLO

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [VisionClient] %(message)s"
)
logger = logging.getLogger("vision.main")

# .env 로드
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "STUDY_ROOM_2026_09_05_v1_0_0")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")


class VisionStudySeatClient:
    """
    정면 웹캠과 YOLOv8n을 활용하여 학습자의 착석, 자세 불균형(거북목/숙임),
    졸음(눈감음/고개숙임 지속)을 감지하고 백엔드에 이벤트를 실시간 전송하는 클라이언트.
    """

    def __init__(self) -> None:
        self.backend_url = BACKEND_URL.rstrip("/")
        self.headers = {
            "X-Device-Api-Key": DEVICE_API_KEY,
            "Content-Type": "application/json"
        }

        # 모델 로드
        logger.info(f"Loading YOLOv8n model from {MODEL_PATH}...")
        self.model = YOLO(MODEL_PATH)

        # 감지 상태 변수
        self.is_occupied: bool = False
        self.posture_status: str = "GOOD"  # "GOOD", "TURTLE_NECK", "UNKNOWN"
        self.drowsiness_detected: bool = False

        # 기준 좌표 및 타이머
        self.base_head_y: Optional[float] = None
        self.head_drop_start_time: Optional[float] = None
        self.eyes_closed_start_time: Optional[float] = None
        self.last_telemetry_time: float = 0.0

        # Haar Cascade (OpenCV 기본 얼굴/눈 감지기 - 졸음 보조 분석)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )

    def send_event(self, event_type: str, detected: bool, count: int = 1, confidence: float = 0.9) -> bool:
        """백엔드로 개별 감지 이벤트를 전송합니다."""
        url = f"{self.backend_url}/api/v1/vision/events"
        payload = {
            "event_type": event_type,
            "detected": detected,
            "count": count,
            "confidence": confidence
        }
        try:
            res = requests.post(url, json=payload, headers=self.headers, timeout=2.0)
            if res.status_code == 200:
                logger.info(f"Event sent [{event_type}]: detected={detected}")
                return True
            else:
                logger.warning(f"Event failed [{event_type}]: HTTP {res.status_code}")
        except Exception as exc:
            logger.warning(f"Connection error sending event [{event_type}]: {exc}")
        return False

    def send_telemetry(self) -> None:
        """PRD 규격의 종합 좌석 텔레메트리를 백엔드로 전송합니다."""
        url = f"{self.backend_url}/api/v1/seat/telemetry"
        payload = {
            "event": "SEAT_TELEMETRY",
            "seat_id": "SEAT_01",
            "is_occupied": self.is_occupied,
            "drowsiness_detected": self.drowsiness_detected,
            "posture_status": self.posture_status,
            "led_brightness": 80,
            "study_time_seconds": 0
        }
        try:
            requests.post(url, json=payload, headers=self.headers, timeout=2.0)
        except Exception:
            pass  # 백그라운드 텔레메트리는 오류 시 조용히 넘김

    def run(self) -> None:
        """비전 감지 메인 루프 실행"""
        logger.info(f"Connecting to camera index {CAMERA_INDEX} via CAP_DSHOW...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

        simulation_mode = False
        if not cap.isOpened():
            logger.warning("=" * 60)
            logger.warning("웹캠을 열 수 없습니다 (카메라 미연결 또는 다른 프로그램 사용 중).")
            logger.warning(">> 가상 시뮬레이션 & 키보드 인터랙션 모드로 자동 전환합니다. <<")
            logger.warning("   [Space] : 착석 ON/OFF 토글")
            logger.warning("   [D]     : 졸음 감지 트리거")
            logger.warning("   [P]     : 자세 불량(거북목) 트리거")
            logger.warning("   [Q]     : 종료")
            logger.warning("=" * 60)
            simulation_mode = True

        window_name = "AI Smart Study Seat - Vision AI Client"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)

        prev_time = time.time()

        try:
            while True:
                now = time.time()
                fps = 1.0 / max(now - prev_time, 0.001)
                prev_time = now

                if not simulation_mode:
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning("프레임을 읽지 못했습니다. 시뮬레이션 모드로 전환합니다.")
                        simulation_mode = True
                        continue
                else:
                    # 가상 시뮬레이션 캔버스 생성 (어두운 스마트 대시보드 룩)
                    frame = np.zeros((600, 800, 3), dtype=np.uint8)
                    frame[:] = (26, 24, 20)  # Dark slate background

                # --------------------------------------------------------------
                # 1. 실제 웹캠 감지 처리
                # --------------------------------------------------------------
                if not simulation_mode:
                    # YOLOv8 추론 (person 클래스만 추론)
                    results = self.model(frame, classes=[0], conf=0.5, verbose=False)
                    boxes = results[0].boxes

                    person_detected = len(boxes) > 0

                    if person_detected:
                        # 가장 큰 사람 바운딩 박스 선택 (메인 학습자)
                        main_box = max(boxes, key=lambda b: (b.xyxy[0][2] - b.xyxy[0][0]) * (b.xyxy[0][3] - b.xyxy[0][1]))
                        x1, y1, x2, y2 = map(int, main_box.xyxy[0].cpu().numpy())
                        head_y = float(y1)

                        # 바운딩 박스 표시
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 100), 2)
                        cv2.putText(frame, "STUDENT OCCUPIED", (x1, max(y1 - 10, 20)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 100), 2)

                        # 기준 높이 자동 보정
                        if self.base_head_y is None:
                            self.base_head_y = head_y
                        else:
                            # 서서히 학습 (지수 평활)
                            self.base_head_y = 0.98 * self.base_head_y + 0.02 * head_y

                        # 착석 상태 전환 감지
                        if not self.is_occupied:
                            self.is_occupied = True
                            self.send_event("person_detected", True, confidence=float(main_box.conf[0]))

                        # --- 자세 분석 (Y축 하강 검사: PRD REQ-2.2) ---
                        # 기준 높이보다 45픽셀 이상 내려가면 고개숙임/거북목 판정
                        if head_y - self.base_head_y > 45:
                            if self.posture_status != "TURTLE_NECK":
                                self.posture_status = "TURTLE_NECK"
                                self.send_event("posture", True)
                        else:
                            if self.posture_status == "TURTLE_NECK":
                                self.posture_status = "GOOD"
                                self.send_event("posture", False)

                        # --- 졸음 분석 (얼굴 내 눈 감김 / 지속성 분석: PRD REQ-2.1) ---
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        person_roi_gray = gray[y1:y2, x1:x2]
                        faces = self.face_cascade.detectMultiScale(person_roi_gray, 1.2, 5)

                        eyes_visible = False
                        if len(faces) > 0:
                            fx, fy, fw, fh = faces[0]
                            face_roi_gray = person_roi_gray[fy:fy + fh, fx:fx + fw]
                            eyes = self.eye_cascade.detectMultiScale(face_roi_gray, 1.1, 4)
                            if len(eyes) >= 1:
                                eyes_visible = True

                        if not eyes_visible:
                            if self.eyes_closed_start_time is None:
                                self.eyes_closed_start_time = now
                            elif now - self.eyes_closed_start_time >= 2.5:
                                if not self.drowsiness_detected:
                                    self.drowsiness_detected = True
                                    self.send_event("drowsiness", True)
                        else:
                            self.eyes_closed_start_time = None
                            if self.drowsiness_detected:
                                self.drowsiness_detected = False
                                self.send_event("drowsiness", False)

                    else:
                        # 사람 미감지 (부재)
                        if self.is_occupied:
                            self.is_occupied = False
                            self.posture_status = "UNKNOWN"
                            self.drowsiness_detected = False
                            self.send_event("person_detected", False)

                # --------------------------------------------------------------
                # 2. 화면 UI 오버레이 (헤드업 디스플레이 정보 출력)
                # --------------------------------------------------------------
                status_color = (0, 255, 128) if self.is_occupied else (150, 150, 150)
                occupied_text = "OCCUPIED" if self.is_occupied else "VACANT (NO PERSON)"

                cv2.putText(frame, "AI SMART STUDY SEAT - VISION HUD", (25, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                cv2.putText(frame, f"Seat Status  : {occupied_text}", (25, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2)

                posture_color = (0, 200, 255) if self.posture_status == "GOOD" else (0, 140, 255)
                cv2.putText(frame, f"Posture      : {self.posture_status}", (25, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, posture_color, 2)

                drowsy_color = (0, 0, 255) if self.drowsiness_detected else (200, 200, 200)
                drowsy_text = "DROWSY WARNING!" if self.drowsiness_detected else "NORMAL"
                cv2.putText(frame, f"Drowsiness   : {drowsy_text}", (25, 145),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, drowsy_color, 2)

                cv2.putText(frame, f"FPS: {fps:.1f} | Backend: {self.backend_url}", (25, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

                # 단축키 안내 표시
                cv2.rectangle(frame, (20, 520), (780, 580), (45, 40, 35), -1)
                cv2.putText(frame, "Shortcuts: [Space] Toggle Seat | [D] Drowsiness | [P] Posture Alert | [Q] Quit",
                            (30, 555), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 220, 150), 1)

                cv2.imshow(window_name, frame)

                # 주기적 텔레메트리 전송 (2초 간격)
                if now - self.last_telemetry_time >= 2.0:
                    self.send_telemetry()
                    self.last_telemetry_time = now

                # --------------------------------------------------------------
                # 3. 키보드 인터랙션 처리 (시뮬레이션 및 수동 테스트)
                # --------------------------------------------------------------
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # 'q' 또는 ESC
                    logger.info("Quitting Vision Client...")
                    break
                elif key == 32:  # 스페이스바 (착석 토글)
                    self.is_occupied = not self.is_occupied
                    logger.info(f"[Manual] Toggled occupied: {self.is_occupied}")
                    self.send_event("person_detected", self.is_occupied)
                elif key == ord('d'):  # 'd' (졸음 토글)
                    self.drowsiness_detected = not self.drowsiness_detected
                    logger.info(f"[Manual] Triggered drowsiness: {self.drowsiness_detected}")
                    self.send_event("drowsiness", self.drowsiness_detected)
                elif key == ord('p'):  # 'p' (자세 불량 토글)
                    new_posture = "TURTLE_NECK" if self.posture_status == "GOOD" else "GOOD"
                    self.posture_status = new_posture
                    is_bad = (new_posture == "TURTLE_NECK")
                    logger.info(f"[Manual] Triggered posture: {self.posture_status}")
                    self.send_event("posture", is_bad)

        finally:
            if not simulation_mode and cap.isOpened():
                cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    client = VisionStudySeatClient()
    client.run()
