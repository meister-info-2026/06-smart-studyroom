import logging
import os
import sys
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

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
MODEL_ONNX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.onnx")


# ==============================================================================
# 한글 텍스트 렌더링 유틸리티 (Pillow 기반)
# ==============================================================================
def put_korean_text(
    img: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_size: int = 18,
    color: Tuple[int, int, int] = (255, 255, 255)
) -> np.ndarray:
    """OpenCV BGR 이미지 위에 한글 텍스트를 깨짐 없이 선명하게 출력합니다."""
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # Windows 기본 한글 폰트 탐색
    font = None
    korean_font_paths = [
        "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕
        "C:/Windows/Fonts/gulim.ttc",        # 굴림
        "C:/Windows/Fonts/batang.ttc",       # 바탕
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    ]
    for p in korean_font_paths:
        if os.path.exists(p):
            try:
                font = ImageFont.truetype(p, font_size)
                break
            except Exception:
                pass

    if font is None:
        font = ImageFont.load_default()

    draw.text(position, text, font=font, fill=color)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


# ==============================================================================
# 초경량 YOLOv8 ONNX 듀얼 추론 엔진 (ONNXRuntime + OpenCV DNN 폴백)
# ==============================================================================
class YOLOv8ONNXDetector:
    """PyTorch/Ultralytics 없이 ONNX Runtime 또는 OpenCV DNN으로 사람을 초고속 검출하는 검출기"""

    def __init__(self, model_path: str, conf_threshold: float = 0.45, iou_threshold: float = 0.45) -> None:
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = (640, 640)
        self.use_ort = False
        self.session = None
        self.net = None

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"ONNX model file not found: {model_path}")

        # 1. ONNX Runtime 우선 로드
        try:
            import onnxruntime as ort
            providers = ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            self.use_ort = True
            logger.info(f"Loaded YOLOv8 ONNX model via ONNXRuntime: {model_path}")
        except Exception as exc:
            # 2. OpenCV DNN 자동 폴백
            logger.warning(f"ONNXRuntime init failed ({exc}). Falling back to cv2.dnn engine.")
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.use_ort = False

    def preprocess(self, img: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Letterbox 패딩 및 NCHW 정규화"""
        h, w = img.shape[:2]
        target_w, target_h = self.input_size

        scale = min(target_w / w, target_h / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        dx, dy = (target_w - nw) // 2, (target_h - nh) // 2

        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        canvas[dy:dy + nh, dx:dx + nw] = resized

        # BGR -> RGB, 0~1 정규화, HWC -> CHW, 배치 차원 추가
        blob = canvas.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        return blob, scale, (dx, dy)

    def detect_persons(self, frame: np.ndarray) -> List[List[float]]:
        """
        프레임 내 사람(person, class 0) 바운딩 박스를 검출합니다.
        반환: [[x1, y1, x2, y2, conf], ...]
        """
        blob, scale, (dx, dy) = self.preprocess(frame)

        if self.use_ort:
            outputs = self.session.run(None, {self.input_name: blob})
            raw = outputs[0]  # shape: [1, 84, 8400]
        else:
            self.net.setInput(blob)
            raw = self.net.forward()

        # [1, 84, 8400] -> [8400, 84]
        predictions = np.squeeze(raw, axis=0).T

        boxes = []
        confidences = []

        # YOLOv8 클래스 0: person (index 4)
        for row in predictions:
            person_score = float(row[4])
            if person_score >= self.conf_threshold:
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                # 원래 프레임 좌표로 스케일 복원
                x1 = int((cx - w / 2 - dx) / scale)
                y1 = int((cy - h / 2 - dy) / scale)
                bw = int(w / scale)
                bh = int(h / scale)

                boxes.append([x1, y1, bw, bh])
                confidences.append(person_score)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.iou_threshold)
        results = []
        if len(indices) > 0:
            for idx in indices.flatten():
                x1, y1, bw, bh = boxes[idx]
                conf = confidences[idx]
                results.append([float(x1), float(y1), float(x1 + bw), float(y1 + bh), float(conf)])

        return results


# ==============================================================================
# 메인 비전 클라이언트 (학습 좌석 감지 & 인터랙션)
# ==============================================================================
class VisionStudySeatClient:
    """
    초경량 ONNX 엔진을 활용하여 학습자의 착석, 자세 불균형(거북목/숙임),
    졸음(눈감음 지속)을 실시간 감지하고 백엔드로 전송하는 클라이언트.
    """

    def __init__(self) -> None:
        self.backend_url = BACKEND_URL.rstrip("/")
        self.headers = {
            "X-Device-Api-Key": DEVICE_API_KEY,
            "Content-Type": "application/json"
        }

        # 초경량 ONNX 모델 로드
        self.detector = YOLOv8ONNXDetector(MODEL_ONNX_PATH, conf_threshold=0.45)

        # 감지 상태 변수
        self.is_occupied: bool = False
        self.posture_status: str = "GOOD"
        self.drowsiness_detected: bool = False

        # 기준 좌표 및 타이머
        self.base_head_y: Optional[float] = None
        self.eyes_closed_start_time: Optional[float] = None
        self.last_telemetry_time: float = 0.0

        # 얼굴/눈 검출기 (OpenCV 내장)
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
            pass

    def run(self) -> None:
        """비전 감지 메인 루프 실행"""
        logger.info(f"Connecting to camera index {CAMERA_INDEX} via CAP_DSHOW...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

        simulation_mode = False
        if not cap.isOpened():
            logger.warning("=" * 60)
            logger.warning("웹캠을 열 수 없습니다 (카메라 미연결 또는 타 프로그램 사용 중).")
            logger.warning(">> 가상 시뮬레이션 & 키보드 인터랙션 모드로 자동 전환합니다. <<")
            logger.warning("   [Space] : 착석 ON/OFF 토글")
            logger.warning("   [D]     : 졸음 감지 트리거")
            logger.warning("   [P]     : 자세 불량(거북목) 트리거")
            logger.warning("   [Q]     : 종료")
            logger.warning("=" * 60)
            simulation_mode = True

        window_name = "AI Smart Study Seat - Vision AI Client (ONNX)"
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
                        simulation_mode = True
                        continue
                else:
                    frame = np.zeros((600, 800, 3), dtype=np.uint8)
                    frame[:] = (26, 24, 20)

                # --------------------------------------------------------------
                # 1. 실제 웹캠 감지 처리 (초경량 ONNX 추론)
                # --------------------------------------------------------------
                if not simulation_mode:
                    persons = self.detector.detect_persons(frame)

                    if persons:
                        # 가장 큰 사람 바운딩 박스 선택
                        main_person = max(persons, key=lambda p: (p[2] - p[0]) * (p[3] - p[1]))
                        x1, y1, x2, y2, conf = map(int, main_person[:4]) + [main_person[4]]
                        head_y = float(y1)

                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 100), 2)
                        frame = put_korean_text(frame, f"학습자 착석 중 ({conf:.2f})", (x1, max(y1 - 25, 10)), font_size=16, color=(0, 240, 120))

                        # 기준 높이 자동 보정
                        if self.base_head_y is None:
                            self.base_head_y = head_y
                        else:
                            self.base_head_y = 0.98 * self.base_head_y + 0.02 * head_y

                        # 착석 전환
                        if not self.is_occupied:
                            self.is_occupied = True
                            self.send_event("person_detected", True, confidence=conf)

                        # 자세 분석 (거북목/숙임: PRD REQ-2.2)
                        if head_y - self.base_head_y > 45:
                            if self.posture_status != "TURTLE_NECK":
                                self.posture_status = "TURTLE_NECK"
                                self.send_event("posture", True)
                        else:
                            if self.posture_status == "TURTLE_NECK":
                                self.posture_status = "GOOD"
                                self.send_event("posture", False)

                        # 졸음 분석 (얼굴 내 눈 감김 지속: PRD REQ-2.1)
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        person_roi = gray[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]

                        eyes_visible = False
                        if person_roi.size > 0:
                            faces = self.face_cascade.detectMultiScale(person_roi, 1.2, 5)
                            if len(faces) > 0:
                                fx, fy, fw, fh = faces[0]
                                face_roi = person_roi[fy:fy + fh, fx:fx + fw]
                                eyes = self.eye_cascade.detectMultiScale(face_roi, 1.1, 4)
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
                        if self.is_occupied:
                            self.is_occupied = False
                            self.posture_status = "UNKNOWN"
                            self.drowsiness_detected = False
                            self.send_event("person_detected", False)

                # --------------------------------------------------------------
                # 2. 한글 HUD 오버레이 (Pillow 선명 렌더링)
                # --------------------------------------------------------------
                frame = put_korean_text(frame, "AI 스마트 학습 좌석 - 비전 HUD (초경량 ONNX)", (25, 20), font_size=20, color=(255, 255, 255))

                seat_status_text = "● 착석 중 (학습 타이머 가동)" if self.is_occupied else "○ 미착석 (대기 상태)"
                seat_color = (100, 255, 150) if self.is_occupied else (180, 180, 180)
                frame = put_korean_text(frame, f"좌석 상태 : {seat_status_text}", (25, 55), font_size=16, color=seat_color)

                posture_text = "바른 자세 (정상)" if self.posture_status == "GOOD" else "⚠️ 거북목/숙임 감지 (등받이 피드백)"
                posture_color = (120, 220, 255) if self.posture_status == "GOOD" else (255, 160, 50)
                frame = put_korean_text(frame, f"자세 상태 : {posture_text}", (25, 85), font_size=16, color=posture_color)

                drowsy_text = "⚠️ 졸음 감지! (방석 진동 & 경고등)" if self.drowsiness_detected else "정상 (눈뜸)"
                drowsy_color = (255, 80, 80) if self.drowsiness_detected else (200, 200, 200)
                frame = put_korean_text(frame, f"졸음 상태 : {drowsy_text}", (25, 115), font_size=16, color=drowsy_color)

                cv2.putText(frame, f"FPS: {fps:.1f} | Engine: ONNX | Backend: {self.backend_url}", (25, 160),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)

                # 단축키 안내 바
                cv2.rectangle(frame, (20, 525), (780, 580), (45, 40, 35), -1)
                frame = put_korean_text(frame, "단축키: [Space] 착석 토글 | [D] 졸음 피드백 | [P] 자세 경고 | [Q] 종료",
                                        (30, 542), font_size=14, color=(255, 220, 150))

                cv2.imshow(window_name, frame)

                # 주기적 텔레메트리 전송 (2초 간격)
                if now - self.last_telemetry_time >= 2.0:
                    self.send_telemetry()
                    self.last_telemetry_time = now

                # --------------------------------------------------------------
                # 3. 키보드 인터랙션 (시뮬레이션 모드 지원)
                # --------------------------------------------------------------
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
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
