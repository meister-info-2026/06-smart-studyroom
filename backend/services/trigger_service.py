import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from db.database import log_vision_event
from iot.provider_factory import get_device_provider
from schemas.models import VisionEventPayload, SeatTelemetryPayload
from websocket_manager import ws_manager

logger = logging.getLogger("backend.services.trigger_service")


class StudySeatTriggerService:
    """
    비전 AI(웹캠)의 감지 이벤트를 수신하여 AGENTS.md 및 PRD 요구사항에 따라
    액추에이터(조명, 진동 모터, 스크린 전원)의 상태를 자동으로 제어하고
    대시보드로 실시간 브로드캐스트하는 트리거 엔진.
    """

    def __init__(self) -> None:
        self.is_occupied: bool = False
        self.last_occupied_time: float = time.time()
        self.last_unoccupied_time: Optional[float] = None
        self.drowsiness_count: int = 0
        self.posture_warning_count: int = 0
        self.session_start_time: Optional[float] = None
        self.total_study_seconds: int = 0
        self.led_brightness: int = 80
        self.current_posture: str = "GOOD"

    async def process_vision_event(self, event: VisionEventPayload) -> Dict[str, Any]:
        """비전 클라이언트로부터 들어온 개별 감지 이벤트를 처리합니다."""
        provider = get_device_provider()

        # 1. DB에 영상인식 이벤트 저장
        await asyncio.to_thread(
            log_vision_event,
            event.event_type,
            event.detected,
            event.count,
            event.confidence
        )

        now = time.time()
        result_message = ""

        # ======================================================================
        # F-1. 착석 감지 및 자동 활성화 / 절전
        # ======================================================================
        if event.event_type in ("person_detected", "seat"):
            if event.detected:
                self.last_unoccupied_time = None
                if not self.is_occupied:
                    self.is_occupied = True
                    if self.session_start_time is None:
                        self.session_start_time = now
                    logger.info("[Trigger] Person detected. Waking up study seat system.")

                    # 착석 시 조명, 스크린, 전원 활성화
                    await provider.set_actuator_state(
                        "rgb_led", "on", {"brightness": self.led_brightness, "color": "#FFFFFF"}, operator="device"
                    )
                    await provider.set_actuator_state("touch_display", "on", None, operator="device")
                    await provider.set_actuator_state("relay_power", "on", None, operator="device")
                    result_message = "착석 감지: 조명 및 스마트 스크린 켜짐"
            else:
                if self.is_occupied:
                    if self.last_unoccupied_time is None:
                        self.last_unoccupied_time = now

                    # 30초 이상 자리 비움 시 절전 모드 전환
                    unoccupied_duration = now - self.last_unoccupied_time
                    if unoccupied_duration >= 30.0:
                        self.is_occupied = False
                        logger.info(f"[Trigger] Unoccupied for {unoccupied_duration:.1f}s. Entering sleep mode.")
                        await provider.set_actuator_state("rgb_led", "off", None, operator="device")
                        await provider.set_actuator_state("touch_display", "off", None, operator="device")
                        await provider.set_actuator_state("vibration_motor_a", "off", None, operator="device")
                        await provider.set_actuator_state("vibration_motor_b", "off", None, operator="device")
                        result_message = "30초 이상 미착석: 절전 모드 전환"

        # ======================================================================
        # F-2. 졸음 감지 및 방석 진동 피드백
        # ======================================================================
        elif event.event_type == "drowsiness":
            if event.detected:
                self.drowsiness_count += 1
                logger.warning(f"[Trigger] Drowsiness detected (Count: {self.drowsiness_count})")
                # 의자 방석 진동 모터 B 작동 & 조명 경고 점멸(alert)
                await provider.set_actuator_state("vibration_motor_b", "on", {"intensity": 100}, operator="device")
                await provider.set_actuator_state("rgb_led", "alert", {"color": "#FF0033", "blink": True}, operator="device")
                result_message = "졸음 감지! 방석 진동 및 조명 경고 작동"

                # 3초 후 진동 자동 해제 태스크 실행
                asyncio.create_task(self._auto_turn_off_vibrator("vibration_motor_b", 3.0))
            else:
                await provider.set_actuator_state("vibration_motor_b", "off", None, operator="device")
                if self.is_occupied:
                    await provider.set_actuator_state("rgb_led", "on", {"brightness": self.led_brightness}, operator="device")

        # ======================================================================
        # F-2. 자세 불균형(숙임/거북목) 감지 및 등받이 진동 피드백
        # ======================================================================
        elif event.event_type == "posture":
            if event.detected:
                self.posture_warning_count += 1
                self.current_posture = "TURTLE_NECK"
                logger.warning(f"[Trigger] Posture warning (Count: {self.posture_warning_count})")
                # 의자 등받이 진동 모터 A 작동
                await provider.set_actuator_state("vibration_motor_a", "on", {"intensity": 80}, operator="device")
                result_message = "자세 불균형 감지! 등받이 진동 작동"

                # 2.5초 후 진동 자동 해제 태스크 실행
                asyncio.create_task(self._auto_turn_off_vibrator("vibration_motor_a", 2.5))
            else:
                self.current_posture = "GOOD"
                await provider.set_actuator_state("vibration_motor_a", "off", None, operator="device")

        # ======================================================================
        # 대시보드 실시간 브로드캐스트
        # ======================================================================
        await self.broadcast_telemetry()

        return {
            "status": "processed",
            "event_type": event.event_type,
            "detected": event.detected,
            "message": result_message
        }

    async def _auto_turn_off_vibrator(self, device_id: str, delay_seconds: float) -> None:
        """진동 모터를 일정 시간 후 자동으로 끕니다."""
        await asyncio.sleep(delay_seconds)
        provider = get_device_provider()
        await provider.set_actuator_state(device_id, "off", None, operator="device")
        # 조명 복구 (졸음 해제 시)
        if device_id == "vibration_motor_b" and self.is_occupied:
            await provider.set_actuator_state(
                "rgb_led", "on", {"brightness": self.led_brightness, "color": "#FFFFFF"}, operator="device"
            )
        await self.broadcast_telemetry()

    async def broadcast_telemetry(self) -> None:
        """전체 디바이스 상태 및 좌석 종합 텔레메트리를 WebSocket으로 브로드캐스트합니다."""
        provider = get_device_provider()
        devices = await provider.get_all_statuses()

        now = time.time()
        study_seconds = 0
        if self.session_start_time and self.is_occupied:
            study_seconds = int(now - self.session_start_time)

        telemetry_data = {
            "type": "SEAT_UPDATE",
            "timestamp": datetime.now().isoformat(),
            "seat": {
                "seat_id": "SEAT_01",
                "is_occupied": self.is_occupied,
                "drowsiness_count": self.drowsiness_count,
                "posture_warning_count": self.posture_warning_count,
                "posture_status": self.current_posture,
                "study_time_seconds": study_seconds,
                "led_brightness": self.led_brightness,
            },
            "devices": devices,
        }
        await ws_manager.broadcast_json(telemetry_data)

    def checkout_session(self, total_study_seconds: Optional[int] = None) -> Dict[str, Any]:
        """학습 세션을 종료하고 요약 통계를 발행합니다 (PRD F-4)."""
        study_time = total_study_seconds or (
            int(time.time() - self.session_start_time) if self.session_start_time else 0
        )
        mins, secs = divmod(study_time, 60)
        hours, mins = divmod(mins, 60)
        formatted_time = f"{hours:02d}:{mins:02d}:{secs:02d}"

        # 집중도 점수 계산 (기본 100점, 졸음 1회당 -10점, 자세 불량 1회당 -5점 감점)
        penalty = (self.drowsiness_count * 10) + (self.posture_warning_count * 5)
        focus_score = max(30, min(100, 100 - penalty))

        session_id = f"SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        report = {
            "session_id": session_id,
            "seat_id": "SEAT_01",
            "total_study_seconds": study_time,
            "study_time_formatted": formatted_time,
            "drowsiness_count": self.drowsiness_count,
            "posture_warning_count": self.posture_warning_count,
            "focus_score": focus_score,
            "checked_out_at": datetime.now().isoformat(),
            "report_url": f"http://localhost:3000/report?session={session_id}",
            "qr_payload": f"SEAT_REPORT:{session_id}:TIME={study_time}:SCORE={focus_score}",
        }

        # 세션 초기화
        self.session_start_time = None
        self.drowsiness_count = 0
        self.posture_warning_count = 0
        self.is_occupied = False

        return report


# 싱글톤 트리거 서비스 인스턴스
trigger_service = StudySeatTriggerService()
