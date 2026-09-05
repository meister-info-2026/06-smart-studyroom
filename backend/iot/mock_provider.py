import asyncio
import logging
from typing import Any, Dict, List, Optional

from iot.base import DeviceProvider
from db.database import (
    get_all_devices,
    get_device,
    update_device_desired_state,
    update_device_current_state,
    log_control_action,
    log_sensor_reading,
)

logger = logging.getLogger("backend.iot.mock_provider")


class MockDeviceProvider(DeviceProvider):
    """
    라즈베리파이 5 하드웨어 연결 전 로컬 윈도우 PC 환경에서 동작하는 Mock 디바이스 제공자.
    액추에이터(조명, 진동 모터 등)의 desired-state 변경 요청을 받아
    DB 상태를 갱신하고 Mock 하드웨어의 current-state를 즉각 동기화합니다.
    """

    def __init__(self) -> None:
        self._initialized = True
        logger.info("MockDeviceProvider initialized for Windows PC simulator mode.")

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """특정 디바이스의 현재 상태 및 정보를 DB에서 조회합니다."""
        # 동기 DB 호출을 비동기 스레드 풀에서 안전하게 실행
        return await asyncio.to_thread(get_device, device_id)

    async def set_actuator_state(
        self,
        device_id: str,
        desired_state: str,
        value: Optional[Any] = None,
        operator: str = "user"
    ) -> Dict[str, Any]:
        """
        액추에이터의 목표 상태를 갱신하고, Mock 환경이므로 즉시 실제 상태(current_state)로 반영합니다.
        제어 이력(control_log)도 함께 저장합니다.
        """
        logger.info(
            f"[MockDevice] set_actuator_state: device={device_id}, "
            f"state={desired_state}, value={value}, operator={operator}"
        )

        def _update_db() -> Optional[Dict[str, Any]]:
            # 1. 목표 상태 및 현재 상태를 DB에 동기화
            update_device_desired_state(device_id, desired_state, value)
            update_device_current_state(device_id, desired_state, value)
            # 2. 제어 로그 기록
            log_control_action(device_id, desired_state, value, operator)
            # 3. 최신 디바이스 정보 조회
            return get_device(device_id)

        device = await asyncio.to_thread(_update_db)
        if not device:
            raise ValueError(f"Device '{device_id}' not found.")

        return device

    async def read_sensor_value(self, device_id: str) -> Dict[str, Any]:
        """
        센서의 최신 측정값을 읽어옵니다.
        Mock 환경에서는 DB에 저장된 현재 상태 또는 가상 센서 값을 반환합니다.
        """
        device = await asyncio.to_thread(get_device, device_id)
        if not device:
            return {"device_id": device_id, "status": "unknown"}

        return {
            "device_id": device_id,
            "name": device.get("name"),
            "kind": device.get("kind"),
            "state": device.get("current_state") or "active",
            "value": device.get("current_value"),
            "updated_at": device.get("updated_at")
        }

    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """등록된 모든 디바이스의 현재 상태 목록을 반환합니다."""
        return await asyncio.to_thread(get_all_devices)
