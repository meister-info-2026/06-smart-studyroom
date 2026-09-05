"use client";

import React, { useState } from "react";
import { DeviceItem } from "@/types/dashboard";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";
import { Power, Sun, Activity, Zap } from "lucide-react";

interface ActuatorCardProps {
  device: DeviceItem;
  onToggle: (deviceId: string, targetState: string, value?: unknown) => Promise<void>;
}

export const ActuatorCard: React.FC<ActuatorCardProps> = ({ device, onToggle }) => {
  const [loading, setLoading] = useState(false);
  const isOn = (device.current_state || "").toLowerCase() === "on" || (device.current_state || "").toLowerCase() === "alert";

  // 밝기 파싱
  let brightness = 80;
  if (device.current_value && typeof device.current_value === "object" && "brightness" in device.current_value) {
    brightness = Number((device.current_value as { brightness: number }).brightness) || 80;
  } else if (typeof device.current_value === "string") {
    try {
      const parsed = JSON.parse(device.current_value);
      if (parsed && typeof parsed.brightness === "number") brightness = parsed.brightness;
    } catch {
      // ignore
    }
  }

  const handleToggle = async () => {
    setLoading(true);
    try {
      const target = isOn ? "off" : "on";
      const val = device.kind === "led" ? { brightness } : undefined;
      await onToggle(device.id, target, val);
    } finally {
      setLoading(false);
    }
  };

  const handleBrightnessChange = async (newVal: number) => {
    try {
      await onToggle(device.id, "on", { brightness: newVal });
    } catch (e) {
      console.error(e);
    }
  };

  // 아이콘 선택
  const getIcon = () => {
    if (device.kind === "led") return <Sun className="w-5 h-5 text-amber-500" />;
    if (device.kind === "vibrator") return <Activity className="w-5 h-5 text-indigo-500" />;
    return <Zap className="w-5 h-5 text-emerald-500" />;
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between">
      {/* 상단: 이름 및 상태 뱃지 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-slate-100">{getIcon()}</div>
          <div>
            <h3 className="font-semibold text-slate-800 text-sm">{device.name}</h3>
            <p className="text-xs text-slate-400 font-mono">{device.id}</p>
          </div>
        </div>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase ${getStatusBadgeClass(
            device.current_state || "off"
          )}`}
        >
          {device.current_state || "OFF"}
        </span>
      </div>

      {/* 중앙: 토글 버튼 및 추가 제어 */}
      <div className="my-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-slate-600">전원 제어</span>
          <button
            onClick={handleToggle}
            disabled={loading}
            className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus:outline-none ${
              isOn ? "bg-emerald-500" : "bg-slate-300"
            }`}
          >
            <span
              className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
                isOn ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>

        {/* LED 밝기 조절 슬라이더 */}
        {device.kind === "led" && isOn && (
          <div className="pt-2 border-t border-slate-100">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>밝기</span>
              <span className="font-semibold text-slate-700">{brightness}%</span>
            </div>
            <input
              type="range"
              min="10"
              max="100"
              value={brightness}
              onChange={(e) => handleBrightnessChange(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
          </div>
        )}
      </div>

      {/* 하단: 마지막 조작 정보 */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <Power className="w-3 h-3" /> 목표: {device.desired_state || "off"}
        </span>
        <span suppressHydrationWarning>
          {device.updated_at ? new Date(device.updated_at).toLocaleTimeString() : "기록 없음"}
        </span>
      </div>
    </div>
  );
};

export default ActuatorCard;
