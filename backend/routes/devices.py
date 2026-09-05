import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from db.database import get_sensor_history, get_control_logs, get_device
from iot.provider_factory import get_device_provider
from schemas.models import DeviceControlRequest, DeviceStateReport
from services.trigger_service import trigger_service
from websocket_manager import ws_manager

logger = logging.getLogger("backend.routes.devices")
router = APIRouter()

DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "STUDY_ROOM_2026_09_05_v1_0_0")


def verify_device_api_key(x_device_api_key: Optional[str] = Header(None)) -> None:
    """하드웨어 및 비전 디바이스 전용 인증 헤더 검증"""
    if not x_device_api_key or x_device_api_key != DEVICE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED_DEVICE", "message": "Invalid or missing X-Device-Api-Key header."}
        )


# ==============================================================================
# 사용자향 엔드포인트 (대시보드 UI 연동)
# ==============================================================================

@router.get("/api/devices")
async def list_devices() -> Dict[str, Any]:
    """등록된 모든 디바이스 목록 및 현재 상태 조회"""
    provider = get_device_provider()
    devices = await provider.get_all_statuses()
    return {"data": devices}


@router.get("/api/devices/{device_id}")
async def get_device_detail(device_id: str) -> Dict[str, Any]:
    """특정 디바이스 상태 및 정보 조회"""
    provider = get_device_provider()
    device = await provider.get_device_status(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": f"Device '{device_id}' not found."}
        )
    return {"data": device}


@router.post("/api/devices/{device_id}/control")
async def control_device(device_id: str, request: DeviceControlRequest) -> Dict[str, Any]:
    """
    대시보드에서 액추에이터 상태를 수동 제어합니다.
    조명 슬라이더(밝기 변경), 진동 모터 토글, 경보 해제 등에 사용됩니다.
    """
    provider = get_device_provider()
    try:
        updated_device = await provider.set_actuator_state(
            device_id=device_id,
            desired_state=request.desired_state,
            value=request.value,
            operator=request.operator
        )

        # LED 밝기 업데이트 시 trigger_service 내부 캐시 동기화
        if device_id == "rgb_led" and request.value and isinstance(request.value, dict):
            if "brightness" in request.value:
                trigger_service.led_brightness = int(request.value["brightness"])

        # WebSocket으로 최신 상태 즉각 브로드캐스트
        await trigger_service.broadcast_telemetry()

        return {"data": updated_device}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": str(exc)}
        )
    except Exception as exc:
        logger.error(f"Failed to control device {device_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "CONTROL_FAILED", "message": str(exc)}
        )


@router.get("/api/devices/{device_id}/history")
async def get_device_history(device_id: str, limit: int = 30) -> Dict[str, Any]:
    """센서 측정 이력 및 제어 이력 조회"""
    sensor_logs = await asyncio.to_thread(get_sensor_history, device_id, limit)
    control_logs = await asyncio.to_thread(get_control_logs, device_id, limit)
    return {
        "data": {
            "device_id": device_id,
            "sensor_readings": sensor_logs,
            "control_log": control_logs,
        }
    }


# ==============================================================================
# 디바이스향 엔드포인트 (라즈베리파이 5 / 하드웨어 데몬 폴링용)
# ==============================================================================

@router.get("/api/v1/devices/{device_id}/desired-state")
async def get_desired_state(
    device_id: str,
    x_device_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    하드웨어가 폴링하여 반영해야 할 목표 상태를 조회합니다.
    """
    verify_device_api_key(x_device_api_key)
    device = await asyncio.to_thread(get_device, device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DEVICE_NOT_FOUND", "message": f"Device '{device_id}' not found."}
        )
    return {
        "data": {
            "device_id": device_id,
            "desired_state": device.get("desired_state"),
            "desired_value": device.get("desired_value"),
            "updated_at": device.get("updated_at")
        }
    }


@router.post("/api/v1/devices/{device_id}/state")
async def report_device_state(
    device_id: str,
    payload: DeviceStateReport,
    x_device_api_key: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    하드웨어가 실제 하드웨어 반영 결과를 백엔드에 보고합니다.
    """
    verify_device_api_key(x_device_api_key)
    from db.database import update_device_current_state
    success = await asyncio.to_thread(
        update_device_current_state,
        device_id,
        payload.current_state,
        payload.current_value
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "UPDATE_FAILED", "message": f"Device '{device_id}' not found."}
        )

    await trigger_service.broadcast_telemetry()
    return {"data": {"device_id": device_id, "current_state": payload.current_state}}
