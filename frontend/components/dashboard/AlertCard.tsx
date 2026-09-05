"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, BellOff } from "lucide-react";

interface AlertCardProps {
  title: string;
  isTriggered: boolean;
  count: number;
  message: string;
  onDismiss: () => Promise<void>;
  deviceKindLabel: string;
}

export const AlertCard: React.FC<AlertCardProps> = ({
  title,
  isTriggered,
  count,
  message,
  onDismiss,
  deviceKindLabel,
}) => {
  return (
    <div
      className={`rounded-2xl border p-5 transition-all duration-300 col-span-1 md:col-span-2 flex flex-col justify-between ${
        isTriggered
          ? "bg-rose-50/90 border-rose-300 shadow-md shadow-rose-100"
          : "bg-white border-slate-200/80 shadow-sm"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`p-2.5 rounded-xl ${
              isTriggered ? "bg-rose-100 text-rose-600 animate-bounce" : "bg-slate-100 text-slate-500"
            }`}
          >
            {isTriggered ? <AlertTriangle className="w-6 h-6" /> : <CheckCircle2 className="w-6 h-6 text-emerald-500" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">{deviceKindLabel}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                  isTriggered ? "bg-rose-200 text-rose-800 animate-pulse" : "bg-emerald-100 text-emerald-800"
                }`}
              >
                {isTriggered ? "⚠️ 경보 발생" : "정상 상태"}
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-800 mt-0.5">{title}</h3>
          </div>
        </div>

        {/* 누적 발생 횟수 카운터 */}
        <div className="text-right">
          <span className="text-xs text-slate-400">누적 경고</span>
          <p className="text-2xl font-black text-slate-800">{count}회</p>
        </div>
      </div>

      <div className="my-3 py-2 px-3.5 rounded-xl bg-slate-50/60 border border-slate-100 flex items-center justify-between">
        <p className={`text-xs ${isTriggered ? "text-rose-700 font-semibold" : "text-slate-600"}`}>
          {isTriggered ? message : "현재 비정상 상태가 감지되지 않았습니다."}
        </p>
        {isTriggered && (
          <button
            onClick={onDismiss}
            className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-rose-600 text-white hover:bg-rose-700 active:scale-95 transition-all shadow-sm"
          >
            <BellOff className="w-3.5 h-3.5" />
            경보 수동 해제
          </button>
        )}
      </div>

      <div className="flex justify-between items-center text-[11px] text-slate-400 pt-2 border-t border-slate-100">
        <span>* 경보 발생 시 방석/등받이 진동 모터가 연동됩니다.</span>
        <span>시스템 자동 모니터링 활성</span>
      </div>
    </div>
  );
};

export default AlertCard;
