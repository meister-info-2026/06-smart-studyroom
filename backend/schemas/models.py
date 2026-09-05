from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# 디바이스 제어 및 상태 모델
# ==============================================================================

class DeviceControlRequest(BaseModel):
    """대시보드 또는 사용자가 액추에이터 상태를 제어할 때 사용하는 요청 스키마"""
    desired_state: str = Field(..., description="목표 상태 (on, off, alert 등)")
    value: Optional[Any] = Field(None, description="추가 파라미터 (밝기, 진동 강도, RGB 색상 등)")
    operator: str = Field("user", description="제어 주체 ('user' 또는 'device')")


class DeviceStateReport(BaseModel):
    """하드웨어 또는 Mock이 실제 반영된 상태를 보고할 때 사용하는 스키마"""
    current_state: str = Field(..., description="현재 실제 상태 (on, off 등)")
    current_value: Optional[Any] = Field(None, description="현재 실제 값")


class DeviceResponse(BaseModel):
    """디바이스 단일 정보 응답 스키마"""
    id: str
    name: str
    kind: str
    desired_state: Optional[str] = None
    current_state: Optional[str] = None
    desired_value: Optional[Any] = None
    current_value: Optional[Any] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ==============================================================================
# 영상인식 이벤트 & 텔레메트리 모델
# ==============================================================================

class VisionEventPayload(BaseModel):
    """웹캠 비전 클라이언트가 백엔드로 전송하는 감지 이벤트 스키마"""
    event_type: str = Field(..., description="이벤트 유형 ('person_detected', 'drowsiness', 'posture')")
    detected: bool = Field(..., description="감지 여부 (True/False)")
    count: int = Field(0, description="감지 횟수 또는 프레임 수")
    confidence: Optional[float] = Field(None, description="신뢰도 (0.0 ~ 1.0)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 분석 정보 (EAR 수치, Y좌표 등)")


class SeatTelemetryPayload(BaseModel):
    """PRD 규격에 맞춘 좌석 상태 종합 텔레메트리 스키마"""
    event: str = Field("SEAT_TELEMETRY", description="이벤트 이름")
    seat_id: str = Field("SEAT_01", description="좌석 식별자")
    is_occupied: bool = Field(..., description="착석 여부")
    drowsiness_detected: bool = Field(False, description="졸음 감지 여부")
    posture_status: str = Field("GOOD", description="자세 상태 ('GOOD', 'TURTLE_NECK', 'UNKNOWN')")
    led_brightness: Optional[int] = Field(80, description="LED 밝기 (0~100)")
    study_time_seconds: Optional[int] = Field(0, description="누적 학습 시간(초)")


# ==============================================================================
# 학습 세션 및 퇴실 리포트 모델 (PRD F-4)
# ==============================================================================

class SessionCheckoutRequest(BaseModel):
    seat_id: str = Field("SEAT_01", description="좌석 식별자")
    total_study_seconds: int = Field(..., description="총 학습 시간(초)")


class SessionCheckoutResponse(BaseModel):
    session_id: str
    seat_id: str
    total_study_seconds: int
    study_time_formatted: str
    drowsiness_count: int
    posture_warning_count: int
    focus_score: int = Field(..., description="집중도 점수 (100점 만점 환산)")
    checked_out_at: datetime
    report_url: str
    qr_payload: str
