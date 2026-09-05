import logging
import os
from typing import Optional

from iot.base import DeviceProvider
from iot.mock_provider import MockDeviceProvider

logger = logging.getLogger("backend.iot.provider_factory")

_cached_provider: Optional[DeviceProvider] = None


def get_device_provider() -> DeviceProvider:
    """
    .env의 DEVICE_MODE 설정값('mock' 또는 'hardware')에 따라
    적절한 DeviceProvider 인스턴스를 반환하는 팩토리 함수입니다.
    """
    global _cached_provider
    if _cached_provider is not None:
        return _cached_provider

    mode = os.getenv("DEVICE_MODE", "mock").lower()

    if mode == "hardware":
        try:
            from iot.hardware_provider import HardwareDeviceProvider
            _cached_provider = HardwareDeviceProvider()
            logger.info("Using HardwareDeviceProvider (Raspberry Pi 5 mode).")
        except ImportError:
            logger.warning(
                "HardwareDeviceProvider not yet implemented. Falling back to MockDeviceProvider."
            )
            _cached_provider = MockDeviceProvider()
    else:
        _cached_provider = MockDeviceProvider()
        logger.info("Using MockDeviceProvider (Local Windows PC simulation mode).")

    return _cached_provider
