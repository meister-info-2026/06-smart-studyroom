"use client";

import React from "react";
import { DeviceItem } from "@/types/dashboard";
import { getStatusBadgeClass } from "@/components/dashboard/statusColor";
import { Camera, Monitor, Radio } from "lucide-react";

interface SensorCardProps {
  device: DeviceItem;
  displayValue?: string;
  unit?: string;
}

export const SensorCard: React.FC<SensorCardProps> = ({ device, displayValue, unit }) => {
  const getIcon = () => {
    if (device.kind === "camera") return <Camera className="w-5 h-5 text-sky-500" />;
    if (device.kind === "display") return <Monitor className="w-5 h-5 text-violet-500" />;
    return <Radio className="w-5 h-5 text-slate-500" />;
  };

  const mainVal = displayValue || (device.current_state === "on" ? "ACTIVE" : "ONLINE");

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between">
      {/* 상단: 이름 및 상태 */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-slate-100">{getIcon()}</div>
          <div>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">센서 장치</span>
            <h3 className="font-semibold text-slate-800 text-sm">{device.name}</h3>
          </div>
        </div>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${getStatusBadgeClass(
            device.current_state || "on"
          )}`}
        >
          {device.current_state || "READY"}
        </span>
      </div>

      {/* 중앙: 큰 수치/상태 및 단위 */}
      <div className="my-3 flex items-baseline gap-1.5">
        <span className="text-3xl font-bold tracking-tight text-slate-800">{mainVal}</span>
        {unit && <span className="text-sm font-medium text-slate-400">{unit}</span>}
      </div>

      {/* 하단: 마지막 갱신 시각 */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span>장치 식별자: {device.id}</span>
        <span suppressHydrationWarning>
          {device.updated_at ? new Date(device.updated_at).toLocaleTimeString() : "정상 동작"}
        </span>
      </div>
    </div>
  );
};

export default SensorCard;
