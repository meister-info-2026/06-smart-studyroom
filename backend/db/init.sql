-- ==============================================================================
-- AI 스마트 학습 좌석 시스템 - MySQL 초기화 스키마 & 시드 데이터
-- ==============================================================================

-- MySQL-only (db-migration 스킬에서 Supabase 전환 시 이 두 줄은 제거한다)
CREATE DATABASE IF NOT EXISTS smart_control
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_control;

-- 1. 디바이스 테이블 (상태는 메모리 변수가 아닌 DB에 영속화)
CREATE TABLE IF NOT EXISTS devices (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  kind VARCHAR(30) NOT NULL,
  desired_state VARCHAR(30) NULL,   -- 대시보드/트리거가 지정한 목표 상태
  current_state VARCHAR(30) NULL,   -- 라즈베리파이(또는 Mock)가 보고한 실제 상태
  desired_value JSON NULL,          -- on/off 외 값 (RGB 색상값, 진동 강도 등)
  current_value JSON NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 센서 측정 로그 테이블
CREATE TABLE IF NOT EXISTS sensor_readings (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  device_id VARCHAR(50) NOT NULL,
  value FLOAT NULL,
  unit VARCHAR(20) NULL,
  value_json JSON NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_sensor_readings_device FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- 3. 제어 이력 로그 테이블
CREATE TABLE IF NOT EXISTS control_log (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  device_id VARCHAR(50) NOT NULL,
  action VARCHAR(50) NOT NULL,
  value JSON NULL,
  actor VARCHAR(20) NOT NULL,        -- 'user' 또는 'device'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_control_log_device FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- 4. 영상인식 이벤트 로그 테이블
CREATE TABLE IF NOT EXISTS vision_events (
  id INT AUTO_INCREMENT PRIMARY KEY, -- MySQL-only
  event_type VARCHAR(50) NOT NULL,   -- 'seat', 'drowsiness', 'posture' 등
  detected BOOLEAN NOT NULL DEFAULT FALSE,
  count INT DEFAULT 0,
  confidence FLOAT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 시드 데이터 (AGENTS.md 팀 정보 기준 디바이스 등록)
-- 시드 INSERT에는 desired_state/current_state를 넣지 않아 재실행 시에도 상태를 덮어쓰지 않음
-- ==============================================================================
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
