import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from db.database import get_vision_events
from schemas.models import VisionEventPayload, SeatTelemetryPayload
from services.trigger_service import trigger_service

logger = logging.getLogger("backend.routes.vision")
router = APIRouter()

DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "STUDY_ROOM_2026_09_05_v1_0_0")


def verify_device_api_key(x_device_api_key: Optional[str] = Header(None)) -> None:
    """비전 클라이언트 디바이스 API 키 검증"""
    if not x_device_api_key or x_device_api_key != DEVICE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED_DEVICE", "message": "Invalid or missing X-Device-Api-Key header."}
        )


@router.post("/api/v1/vision/events")
async def receive_vision_event(
    payload: VisionEventPayload,
    x_device_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    웹캠 비전 클라이언트로부터 착석, 졸음, 자세 불균형 감지 이벤트를 수신하고
    트리거 규칙에 따라 액추에이터 상태를 즉시 제어 및 브로드캐스트합니다.
    """
    verify_device_api_key(x_device_api_key)
    result = await trigger_service.process_vision_event(payload)
    return {"data": result}


@router.post("/api/v1/seat/telemetry")
async def receive_seat_telemetry(
    payload: SeatTelemetryPayload,
    x_device_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    PRD 규격의 종합 SEAT_TELEMETRY 패킷을 수신하여 좌석 상태를 동기화합니다.
    """
    verify_device_api_key(x_device_api_key)

    # 1. 착석 상태 반영
    await trigger_service.process_vision_event(
        VisionEventPayload(event_type="person_detected", detected=payload.is_occupied)
    )

    # 2. 졸음 상태 반영
    if payload.drowsiness_detected:
        await trigger_service.process_vision_event(
            VisionEventPayload(event_type="drowsiness", detected=True)
        )

    # 3. 자세 상태 반영
    if payload.posture_status == "TURTLE_NECK":
        await trigger_service.process_vision_event(
            VisionEventPayload(event_type="posture", detected=True)
        )

    return {"data": {"status": "telemetry_synced", "seat_id": payload.seat_id}}


@router.get("/api/v1/vision/events")
async def list_recent_vision_events(limit: int = 20) -> Dict[str, Any]:
    """최근 발생한 영상인식 감지 이벤트 목록을 반환합니다."""
    events = await asyncio.to_thread(get_vision_events, limit)
    return {"data": events}
