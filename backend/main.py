import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List

# ==============================================================================
# sys.path 자동 경로 주입 (어느 디렉토리에서 실행하든 절대/상대 경로 임포트 오류 방지)
# ==============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from routes.devices import router as devices_router
from routes.vision import router as vision_router
from routes.session import router as session_router
from services.trigger_service import trigger_service
from websocket_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("backend.main")

# CORS 허용 출처
DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def get_allowed_origins() -> List[str]:
    """.env의 CORS_ALLOW_ORIGINS를 파싱해 허용 출처 목록을 반환합니다."""
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 시작 및 종료 수명주기 관리"""
    logger.info("Initializing Smart IoT & Vision Control System Backend...")
    try:
        # 데이터베이스 스키마 및 디바이스 시드 자동 점검/초기화
        await asyncio.to_thread(init_db)
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error(f"Database initialization warning (XAMPP running?): {exc}")

    yield

    logger.info("Shutting down Smart IoT & Vision Control System Backend.")


app = FastAPI(
    title="AI Smart Study Seat System API",
    version="1.0.0",
    description="AI 스마트 학습 좌석: 비전 AI 감지, IoT 액추에이터 제어, 실시간 대시보드 백엔드 API",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(devices_router, tags=["Devices"])
app.include_router(vision_router, tags=["Vision & Telemetry"])
app.include_router(session_router, tags=["Study Session"])


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """백엔드 서버 헬스체크 엔드포인트"""
    return {
        "status": "ok",
        "message": "AI Smart Study Seat Backend is running healthy.",
        "mode": os.getenv("DEVICE_MODE", "mock"),
    }


@app.get("/")
async def root() -> Dict[str, Any]:
    """루트 안내 엔드포인트"""
    return {
        "message": "AI Smart Study Seat Backend is active.",
        "docs_url": "/docs",
        "health_url": "/health",
        "ws_url": "/ws"
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """실시간 디바이스 상태 및 좌석 텔레메트리 스트리밍용 WebSocket 엔드포인트"""
    await ws_manager.connect(websocket)
    try:
        # 클라이언트 연결 즉시 현재 최신 텔레메트리 전송
        await trigger_service.broadcast_telemetry()
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"WebSocket connection closed with error: {exc}")
        ws_manager.disconnect(websocket)
