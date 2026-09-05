import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Union

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

# .env 로드 (backend/.env)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

logger = logging.getLogger("backend.db.database")

# ==============================================================================
# 데이터베이스 접속 설정 (기본값 설정 및 환경변수 주입)
# ==============================================================================
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "smart_control")


@contextmanager
def get_db_connection() -> Generator[pymysql.connections.Connection, None, None]:
    """
    MySQL/MariaDB 커넥션 컨텍스트 매니저.
    트랜잭션 커밋 및 롤백, 안전한 연결 종료를 보장합니다.
    """
    connection = None
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
        yield connection
        connection.commit()
    except Exception as exc:
        if connection:
            connection.rollback()
        logger.error(f"Database connection error: {exc}", exc_info=True)
        raise exc
    finally:
        if connection:
            connection.close()


def init_db() -> None:
    """
    서버 시작 시 호출되어 테이블 존재 여부를 확인하고,
    필요한 기본 테이블 생성 및 디바이스 시드 데이터를 삽입합니다.
    """
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS devices (
      id VARCHAR(50) PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      kind VARCHAR(30) NOT NULL,
      desired_state VARCHAR(30) NULL,
      current_state VARCHAR(30) NULL,
      desired_value JSON NULL,
      current_value JSON NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sensor_readings (
      id INT AUTO_INCREMENT PRIMARY KEY,
      device_id VARCHAR(50) NOT NULL,
      value FLOAT NULL,
      unit VARCHAR(20) NULL,
      value_json JSON NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_sensor_readings_device FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS control_log (
      id INT AUTO_INCREMENT PRIMARY KEY,
      device_id VARCHAR(50) NOT NULL,
      action VARCHAR(50) NOT NULL,
      value JSON NULL,
      actor VARCHAR(20) NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_control_log_device FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS vision_events (
      id INT AUTO_INCREMENT PRIMARY KEY,
      event_type VARCHAR(50) NOT NULL,
      detected BOOLEAN NOT NULL DEFAULT FALSE,
      count INT DEFAULT 0,
      confidence FLOAT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """

    seed_devices_sql = """
    INSERT INTO devices (id, name, kind) VALUES
      ('rgb_led', 'RGB LED 바(스탠드 조명)', 'led'),
      ('vibration_motor_a', '소형 진동 모터 A(등받이 매립)', 'vibrator'),
      ('vibration_motor_b', '소형 진동 모터 B(방석 매립)', 'vibrator'),
      ('relay_power', '릴레이/MOSFET 모듈', 'relay'),
      ('webcam_front', '정면 USB 웹캠', 'camera'),
      ('touch_display', '매립형 터치 디스플레이', 'display')
    ON DUPLICATE KEY UPDATE
      name = VALUES(name),
      kind = VALUES(kind);
    """

    try:
        # DB가 존재하지 않을 경우를 대비해 먼저 데이터베이스를 생성
        admin_conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )
        with admin_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        admin_conn.close()

        # 테이블 및 시드 데이터 적용
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 다중 구문 개별 실행
                for statement in create_tables_sql.strip().split(";"):
                    stmt = statement.strip()
                    if stmt:
                        cursor.execute(stmt)
                cursor.execute(seed_devices_sql)
        logger.info("Database schema and seed devices initialized successfully.")
    except Exception as exc:
        logger.error(f"Failed to initialize database: {exc}", exc_info=True)
        raise exc


# ==============================================================================
# 디바이스 제어 및 조회 헬퍼 함수
# ==============================================================================

def get_all_devices() -> List[Dict[str, Any]]:
    """모든 디바이스 목록과 현재/목표 상태를 조회합니다."""
    query = "SELECT * FROM devices ORDER BY created_at ASC"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            return list(rows)


def get_device(device_id: str) -> Optional[Dict[str, Any]]:
    """특정 디바이스의 정보를 조회합니다."""
    query = "SELECT * FROM devices WHERE id = %s"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (device_id,))
            row = cursor.fetchone()
            return row


def update_device_desired_state(
    device_id: str,
    desired_state: str,
    desired_value: Any = None
) -> bool:
    """
    대시보드 또는 트리거 로직에서 디바이스의 목표 상태(desired_state)를 갱신합니다.
    """
    value_json_str = json.dumps(desired_value, ensure_ascii=False) if desired_value is not None else None
    query = """
    UPDATE devices
    SET desired_state = %s,
        desired_value = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(query, (desired_state, value_json_str, device_id))
            return affected > 0


def update_device_current_state(
    device_id: str,
    current_state: str,
    current_value: Any = None
) -> bool:
    """
    라즈베리파이 또는 Mock 하드웨어가 실제 반영된 상태(current_state)를 보고할 때 갱신합니다.
    """
    value_json_str = json.dumps(current_value, ensure_ascii=False) if current_value is not None else None
    query = """
    UPDATE devices
    SET current_state = %s,
        current_value = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(query, (current_state, value_json_str, device_id))
            return affected > 0


# ==============================================================================
# 센서, 제어 로그, 영상 이벤트 헬퍼 함수
# ==============================================================================

def log_sensor_reading(
    device_id: str,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    value_json: Optional[Union[Dict[str, Any], List[Any]]] = None
) -> None:
    """
    센서 측정값을 DB에 기록합니다.
    단일 수치 센서는 value+unit, 복합 센서는 value_json에 담아 저장합니다.
    """
    json_str = json.dumps(value_json, ensure_ascii=False) if value_json is not None else None
    query = """
    INSERT INTO sensor_readings (device_id, value, unit, value_json)
    VALUES (%s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (device_id, value, unit, json_str))


def log_control_action(
    device_id: str,
    action: str,
    value: Any = None,
    actor: str = "user"
) -> None:
    """
    액추에이터 제어 명령 이력을 DB에 기록합니다.
    actor는 'user' 또는 'device'로 명시합니다.
    """
    val_json_str = json.dumps(value, ensure_ascii=False) if value is not None else None
    query = """
    INSERT INTO control_log (device_id, action, value, actor)
    VALUES (%s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (device_id, action, val_json_str, actor))


def get_sensor_history(device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """특정 센서의 최근 측정 이력을 최신순으로 조회합니다."""
    query = """
    SELECT id, device_id, value, unit, value_json, created_at
    FROM sensor_readings
    WHERE device_id = %s
    ORDER BY created_at DESC
    LIMIT %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (device_id, limit))
            rows = cursor.fetchall()
            return list(rows)


def log_vision_event(
    event_type: str,
    detected: bool,
    count: int = 0,
    confidence: Optional[float] = None
) -> None:
    """
    영상인식 클라이언트(웹캠)로부터 수신된 감지 이벤트를 기록합니다.
    """
    query = """
    INSERT INTO vision_events (event_type, detected, count, confidence)
    VALUES (%s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (event_type, detected, count, confidence))


def get_vision_events(limit: int = 50) -> List[Dict[str, Any]]:
    """최근 발생한 영상인식 이벤트 목록을 조회합니다."""
    query = """
    SELECT id, event_type, detected, count, confidence, created_at
    FROM vision_events
    ORDER BY created_at DESC
    LIMIT %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return list(rows)


def get_control_logs(device_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """최근 제어 이력을 조회합니다. device_id 지정 시 해당 디바이스 이력만 필터링합니다."""
    if device_id:
        query = """
        SELECT id, device_id, action, value, actor, created_at
        FROM control_log
        WHERE device_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """
        params = (device_id, limit)
    else:
        query = """
        SELECT id, device_id, action, value, actor, created_at
        FROM control_log
        ORDER BY created_at DESC
        LIMIT %s
        """
        params = (limit,)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return list(rows)
