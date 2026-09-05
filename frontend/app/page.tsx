"use client";

import React from "react";
import ConnectionBadge from "@/components/dashboard/ConnectionBadge";
import StudyTimerCockpit from "@/components/dashboard/StudyTimerCockpit";
import ActuatorCard from "@/components/dashboard/ActuatorCard";
import SensorCard from "@/components/dashboard/SensorCard";
import AlertCard from "@/components/dashboard/AlertCard";
import VisionEventLogs from "@/components/dashboard/VisionEventLogs";
import { useSmartDeviceSocket } from "@/hooks/useSmartDeviceSocket";
import { Armchair, Sparkles } from "lucide-react";

export default function DashboardPage() {
  const { connected, devices, telemetry, visionLogs, controlActuator } = useSmartDeviceSocket();

  // 액추에이터와 센서 분리
  const actuators = devices.filter((d) => ["led", "vibrator", "relay"].includes(d.kind));
  const sensors = devices.filter((d) => ["camera", "display"].includes(d.kind));

  // 조명 밝기 실시간 제어
  const handleBrightnessChange = async (newVal: number) => {
    await controlActuator("rgb_led", "on", { brightness: newVal });
  };

  // 퇴실 세션 요청
  const handleCheckout = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/session/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seat_id: "SEAT_01", total_study_seconds: telemetry.study_time_seconds }),
      });
      if (res.ok) {
        const json = await res.json();
        return json.data;
      }
    } catch (e) {
      console.error("Checkout failed:", e);
    }
    return null;
  };

  // 경보 수동 해제 핸들러
  const handleDismissDrowsiness = async () => {
    await controlActuator("vibration_motor_b", "off");
    if (telemetry.is_occupied) {
      await controlActuator("rgb_led", "on", { brightness: telemetry.led_brightness });
    }
  };

  const handleDismissPosture = async () => {
    await controlActuator("vibration_motor_a", "off");
  };

  const isDrowsyActive = devices.some(
    (d) => d.id === "vibration_motor_b" && (d.current_state || "").toLowerCase() === "on"
  );
  const isPostureActive = devices.some(
    (d) => d.id === "vibration_motor_a" && (d.current_state || "").toLowerCase() === "on"
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      {/* 최상단 네비게이션 & 연결 상태 바 */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200/80 px-6 py-4 mb-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-gradient-to-tr from-indigo-600 to-violet-500 rounded-2xl text-white shadow-md shadow-indigo-500/20">
              <Armchair className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-extrabold text-slate-900 tracking-tight">
                  AI 스마트 학습 좌석
                </h1>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5" /> 1차 Mock 완성본
                </span>
              </div>
              <p className="text-xs text-slate-500">
                온디바이스 비전 AI 기반 실시간 졸음·자세 교정 및 몰입 케어 대시보드
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ConnectionBadge connected={connected} />
          </div>
        </div>
      </header>

      {/* 메인 대시보드 컨테이너 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6">
        {/* 1. 스마트 좌석 콕핏 (타이머, 집중도, 조명 슬라이더, 퇴실 버튼) */}
        <StudyTimerCockpit
          telemetry={telemetry}
          onBrightnessChange={handleBrightnessChange}
          onCheckout={handleCheckout}
        />

        {/* 2. 핵심 헬스케어 경보 카드 (졸음 / 자세 불량) */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <AlertCard
            title="졸음 감지 & 방석 진동 피드백"
            isTriggered={isDrowsyActive}
            count={telemetry.drowsiness_count}
            message="졸음이 감지되어 방석 진동 모터와 경고 조명이 작동 중입니다."
            onDismiss={handleDismissDrowsiness}
            deviceKindLabel="의자 방석 햅틱 케어"
          />
          <AlertCard
            title="자세 불균형 & 등받이 교정 피드백"
            isTriggered={isPostureActive || telemetry.posture_status === "TURTLE_NECK"}
            count={telemetry.posture_warning_count}
            message="머리 Y축 하강(거북목/숙임)이 감지되어 등받이 진동이 작동 중입니다."
            onDismiss={handleDismissPosture}
            deviceKindLabel="의자 등받이 자세 케어"
          />
        </div>

        {/* 3. 액추에이터 제어 카드 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">제어 대상 액추에이터 (Actuators)</h2>
              <p className="text-xs text-slate-500">대시보드 수동 조작 및 비전 AI 트리거와 동기화되는 장치들</p>
            </div>
            <span className="text-xs text-slate-400 font-mono">총 {actuators.length}개</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {actuators.map((device) => (
              <ActuatorCard
                key={device.id}
                device={device}
                onToggle={async (id, state, val) => {
                  await controlActuator(id, state, val);
                }}
              />
            ))}
          </div>
        </div>

        {/* 4. 센서 모니터링 섹션 */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">모니터링 센서 (Sensors)</h2>
              <p className="text-xs text-slate-500">착석, 자세, 디스플레이 입력을 담당하는 장치 상태</p>
            </div>
            <span className="text-xs text-slate-400 font-mono">총 {sensors.length}개</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
            {sensors.map((device) => (
              <SensorCard
                key={device.id}
                device={device}
                displayValue={
                  device.kind === "camera"
                    ? telemetry.is_occupied
                      ? "착석 감지 중"
                      : "대기 모드"
                    : device.current_state === "on"
                    ? "터치 화면 ON"
                    : "절전 화면 OFF"
                }
              />
            ))}
          </div>
        </div>

        {/* 5. 실시간 영상인식 이벤트 로그 */}
        <VisionEventLogs logs={visionLogs} />
      </main>
    </div>
  );
}
