"use client";

import React from "react";
import { VisionEventLog } from "@/types/dashboard";
import { Eye, ShieldAlert, User, Clock } from "lucide-react";

interface VisionEventLogsProps {
  logs: VisionEventLog[];
}

export const VisionEventLogs: React.FC<VisionEventLogsProps> = ({ logs }) => {
  const getEventMeta = (type: string) => {
    switch (type) {
      case "person_detected":
      case "seat":
        return { label: "착석 감지", icon: <User className="w-4 h-4 text-emerald-500" /> };
      case "drowsiness":
        return { label: "졸음 감지 (방석 피드백)", icon: <Eye className="w-4 h-4 text-rose-500" /> };
      case "posture":
        return { label: "자세 불균형 (거북목 경고)", icon: <ShieldAlert className="w-4 h-4 text-amber-500" /> };
      default:
        return { label: type, icon: <Clock className="w-4 h-4 text-slate-400" /> };
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900">실시간 영상인식 감지 로그</h3>
          <p className="text-xs text-slate-500">정면 웹캠 비전 AI(YOLOv8)가 감지한 실시간 이벤트 스트림</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">
          최근 {logs.length}건
        </span>
      </div>

      <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto pr-1">
        {logs.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
            아직 수신된 영상인식 감지 이벤트가 없습니다.
          </div>
        ) : (
          logs.map((item, idx) => {
            const meta = getEventMeta(item.event_type);
            return (
              <div key={item.id || idx} className="py-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-slate-50">{meta.icon}</div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{meta.label}</p>
                    <p className="text-xs text-slate-400 font-mono">type: {item.event_type}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      item.detected
                        ? "bg-rose-50 text-rose-700 border border-rose-200 font-bold"
                        : "bg-slate-50 text-slate-600 border border-slate-200"
                    }`}
                  >
                    {item.detected ? "감지됨 (Active)" : "해제됨 (Clear)"}
                  </span>
                  <span className="text-xs text-slate-400 whitespace-nowrap" suppressHydrationWarning>
                    {item.created_at ? new Date(item.created_at).toLocaleTimeString() : "방금 전"}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default VisionEventLogs;
