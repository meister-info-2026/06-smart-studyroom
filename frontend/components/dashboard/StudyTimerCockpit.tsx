"use client";

import React, { useState, useEffect } from "react";
import QRCode from "qrcode";
import { SeatTelemetry, SessionReport } from "@/types/dashboard";
import { Timer, UserCheck, UserX, Award, LogOut, X, Sparkles, Sliders } from "lucide-react";

interface StudyTimerCockpitProps {
  telemetry: SeatTelemetry;
  onBrightnessChange: (val: number) => Promise<void>;
  onCheckout: () => Promise<SessionReport | null>;
}

export const StudyTimerCockpit: React.FC<StudyTimerCockpitProps> = ({
  telemetry,
  onBrightnessChange,
  onCheckout,
}) => {
  const [report, setReport] = useState<SessionReport | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string>("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [localSeconds, setLocalSeconds] = useState(telemetry.study_time_seconds);

  // 초 단위 자체 카운터 동기화
  useEffect(() => {
    setLocalSeconds(telemetry.study_time_seconds);
  }, [telemetry.study_time_seconds]);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (telemetry.is_occupied) {
      interval = setInterval(() => {
        setLocalSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [telemetry.is_occupied]);

  const formatSeconds = (sec: number) => {
    const hours = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const handleCheckoutClick = async () => {
    const res = await onCheckout();
    if (res) {
      setReport(res);
      try {
        const url = await QRCode.toDataURL(res.qr_payload, { width: 220, margin: 2 });
        setQrDataUrl(url);
      } catch (e) {
        console.error("QR Code generation error:", e);
      }
      setIsModalOpen(true);
    }
  };

  // 집중도 상태 색상/텍스트
  const getFocusBadge = () => {
    if (telemetry.drowsiness_count > 2) {
      return { label: "집중도 저하 (졸음 주의)", color: "text-rose-600 bg-rose-50 border-rose-200" };
    }
    if (telemetry.posture_status === "TURTLE_NECK") {
      return { label: "자세 불균형 (거북목 경고)", color: "text-amber-600 bg-amber-50 border-amber-200" };
    }
    return { label: "최상의 몰입 상태", color: "text-emerald-600 bg-emerald-50 border-emerald-200" };
  };

  const focusInfo = getFocusBadge();

  return (
    <>
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white rounded-3xl p-6 sm:p-8 shadow-xl border border-slate-700/50 mb-8 relative overflow-hidden">
        {/* 배경 은은한 글로우 데코 */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-72 h-72 bg-emerald-500/10 rounded-full blur-2xl -ml-20 -mb-20 pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          {/* 좌측: 착석 상태 및 타이머 */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
                  telemetry.is_occupied
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                    : "bg-slate-700/50 text-slate-300 border-slate-600"
                }`}
              >
                {telemetry.is_occupied ? (
                  <>
                    <UserCheck className="w-3.5 h-3.5 text-emerald-400" /> 착석 중 (학습 타이머 작동 중)
                  </>
                ) : (
                  <>
                    <UserX className="w-3.5 h-3.5 text-slate-400" /> 미착석 (대기 모드)
                  </>
                )}
              </span>

              <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold border ${focusInfo.color}`}>
                <Sparkles className="w-3 h-3" />
                {focusInfo.label}
              </span>
            </div>

            <div>
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
                <Timer className="w-3.5 h-3.5" /> 누적 학습 시간
              </span>
              <div className="text-4xl sm:text-6xl font-black font-mono tracking-tight text-white mt-1" suppressHydrationWarning>
                {formatSeconds(localSeconds)}
              </div>
            </div>
          </div>

          {/* 우측: 조명 슬라이더 제어 및 퇴실 버튼 */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-5 bg-white/5 backdrop-blur-md p-4 sm:p-5 rounded-2xl border border-white/10">
            {/* LED 스탠드 밝기 조절 */}
            <div className="space-y-2 min-w-[180px]">
              <div className="flex justify-between text-xs text-slate-300">
                <span className="flex items-center gap-1">
                  <Sliders className="w-3.5 h-3.5 text-amber-400" /> 스탠드 조명 밝기
                </span>
                <span className="font-bold text-amber-300">{telemetry.led_brightness}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={telemetry.led_brightness}
                onChange={(e) => onBrightnessChange(Number(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
            </div>

            {/* 퇴실하기 버튼 */}
            <button
              onClick={handleCheckoutClick}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-rose-500 to-indigo-600 hover:from-rose-600 hover:to-indigo-700 text-white font-bold text-sm shadow-lg hover:shadow-indigo-500/25 active:scale-95 transition-all"
            >
              <LogOut className="w-4 h-4" />
              퇴실 & 리포트 발행
            </button>
          </div>
        </div>
      </div>

      {/* 학습 리포트 & QR 코드 모달 (PRD F-4) */}
      {isModalOpen && report && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-sm p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-8 text-slate-800 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute top-5 right-5 p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="text-center mb-6">
              <div className="inline-flex p-3 bg-indigo-50 text-indigo-600 rounded-2xl mb-2">
                <Award className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-extrabold text-slate-900">학습 세션 리포트</h3>
              <p className="text-xs text-slate-500 mt-1">
                오늘의 스마트 학습 좌석 집중도 케어 요약입니다.
              </p>
            </div>

            {/* 통계 요약 박스 */}
            <div className="grid grid-cols-2 gap-3 mb-6">
              <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100 text-center">
                <span className="text-xs text-slate-400 font-medium">총 공부 시간</span>
                <p className="text-xl font-black text-slate-800 mt-0.5">{report.study_time_formatted}</p>
              </div>
              <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100 text-center">
                <span className="text-xs text-slate-400 font-medium">종합 집중도 점수</span>
                <p className="text-xl font-black text-emerald-600 mt-0.5">{report.focus_score}점</p>
              </div>
              <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100 text-center">
                <span className="text-xs text-slate-400 font-medium">졸음 방석 피드백</span>
                <p className="text-xl font-black text-rose-600 mt-0.5">{report.drowsiness_count}회</p>
              </div>
              <div className="bg-slate-50 p-3.5 rounded-2xl border border-slate-100 text-center">
                <span className="text-xs text-slate-400 font-medium">등받이 자세 교정</span>
                <p className="text-xl font-black text-amber-600 mt-0.5">{report.posture_warning_count}회</p>
              </div>
            </div>

            {/* QR 코드 렌더링 */}
            <div className="flex flex-col items-center justify-center p-4 bg-slate-50 rounded-2xl border border-slate-100 mb-6">
              {qrDataUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={qrDataUrl} alt="Session Report QR" className="w-44 h-44 rounded-lg shadow-sm" />
              ) : (
                <div className="w-44 h-44 bg-slate-200 animate-pulse rounded-lg flex items-center justify-center text-xs text-slate-400">
                  QR 생성 중...
                </div>
              )}
              <p className="text-[11px] text-slate-500 mt-2 font-medium">
                스마트폰 카메라로 스캔하여 모바일 대시보드로 연동하세요.
              </p>
            </div>

            <button
              onClick={() => setIsModalOpen(false)}
              className="w-full py-3 rounded-xl bg-slate-900 text-white font-bold text-sm hover:bg-slate-800 transition-colors"
            >
              확인 완료
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default StudyTimerCockpit;
