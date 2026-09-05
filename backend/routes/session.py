import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from schemas.models import SessionCheckoutRequest, SessionCheckoutResponse
from services.trigger_service import trigger_service

logger = logging.getLogger("backend.routes.session")
router = APIRouter()

# 세션 리포트 보관소 (간이 메모리 저장소)
SESSION_STORE: Dict[str, Dict[str, Any]] = {}


@router.post("/api/session/checkout")
async def checkout_study_session(payload: Optional[SessionCheckoutRequest] = None) -> Dict[str, Any]:
    """
    학습 좌석에서 '퇴실' 시 호출되어 현재 세션의 학습 요약 통계(공부 시간, 졸음 횟수, 자세 경고, 집중도 점수)를
    계산하고 고유 QR 코드 페이로드를 생성하여 반환합니다 (PRD F-4).
    """
    total_seconds = payload.total_study_seconds if payload else None
    report = trigger_service.checkout_session(total_seconds)
    SESSION_STORE[report["session_id"]] = report

    logger.info(f"Session {report['session_id']} checked out successfully: Score {report['focus_score']}")
    return {"data": report}


@router.get("/api/session/status")
async def get_current_session_status() -> Dict[str, Any]:
    """현재 좌석의 실시간 학습 진행 상태를 반환합니다."""
    return {
        "data": {
            "seat_id": "SEAT_01",
            "is_occupied": trigger_service.is_occupied,
            "drowsiness_count": trigger_service.drowsiness_count,
            "posture_warning_count": trigger_service.posture_warning_count,
            "current_posture": trigger_service.current_posture,
            "session_active": trigger_service.session_start_time is not None,
        }
    }


@router.get("/api/session/{session_id}")
async def get_session_report(session_id: str) -> Dict[str, Any]:
    """발급된 학습 세션 리포트 상세 정보를 조회합니다."""
    if session_id not in SESSION_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": f"Session report '{session_id}' not found."}
        )
    return {"data": SESSION_STORE[session_id]}
