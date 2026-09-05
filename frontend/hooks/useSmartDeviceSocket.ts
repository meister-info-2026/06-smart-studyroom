"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { DeviceItem, SeatTelemetry, VisionEventLog } from "@/types/dashboard";

const BACKEND_HTTP = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const BACKEND_WS = BACKEND_HTTP.replace(/^http/, "ws") + "/ws";

export function useSmartDeviceSocket() {
  const [connected, setConnected] = useState<boolean>(false);
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [telemetry, setTelemetry] = useState<SeatTelemetry>({
    seat_id: "SEAT_01",
    is_occupied: false,
    drowsiness_count: 0,
    posture_warning_count: 0,
    posture_status: "GOOD",
    study_time_seconds: 0,
    led_brightness: 80,
  });
  const [visionLogs, setVisionLogs] = useState<VisionEventLog[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const connectWebSocketRef = useRef<() => void>(() => {});

  // 초기 REST 데이터 로드
  const fetchInitialData = useCallback(async () => {
    try {
      // 1. 디바이스 목록
      const devRes = await fetch(`${BACKEND_HTTP}/api/devices`);
      if (devRes.ok) {
        const json = await devRes.json();
        if (json.data) setDevices(json.data);
      }

      // 2. 비전 이벤트 목록
      const visRes = await fetch(`${BACKEND_HTTP}/api/v1/vision/events?limit=15`);
      if (visRes.ok) {
        const json = await visRes.json();
        if (json.data) setVisionLogs(json.data);
      }

      // 3. 세션 상태
      const sessRes = await fetch(`${BACKEND_HTTP}/api/session/status`);
      if (sessRes.ok) {
        const json = await sessRes.json();
        if (json.data) {
          setTelemetry((prev) => ({
            ...prev,
            is_occupied: json.data.is_occupied,
            drowsiness_count: json.data.drowsiness_count,
            posture_warning_count: json.data.posture_warning_count,
            posture_status: json.data.current_posture,
          }));
        }
      }
    } catch (err) {
      console.warn("Failed to fetch initial REST data:", err);
    }
  }, []);

  // WebSocket 연결 함수 정의
  const connectWebSocket = useCallback(() => {
    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN ||
        socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    try {
      const ws = new WebSocket(BACKEND_WS);

      ws.onopen = () => {
        setConnected(true);
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
        fetchInitialData();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "SEAT_UPDATE") {
            if (message.seat) {
              setTelemetry(message.seat);
            }
            if (message.devices) {
              setDevices(message.devices);
            }
          }
        } catch (e) {
          console.warn("Failed to parse WebSocket message:", e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        socketRef.current = null;
        if (!reconnectTimeoutRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectTimeoutRef.current = null;
            connectWebSocketRef.current();
          }, 2500);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      socketRef.current = ws;
    } catch (error) {
      console.warn("WebSocket init error, scheduling reconnect:", error);
      setConnected(false);
      if (!reconnectTimeoutRef.current) {
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connectWebSocketRef.current();
        }, 3000);
      }
    }
  }, [fetchInitialData]);

  useEffect(() => {
    connectWebSocketRef.current = connectWebSocket;
  }, [connectWebSocket]);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connectWebSocket]);

  // 디바이스 수동 제어 함수
  const controlActuator = async (
    deviceId: string,
    desiredState: string,
    value?: unknown
  ) => {
    try {
      const res = await fetch(`${BACKEND_HTTP}/api/devices/${deviceId}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ desired_state: desiredState, value, operator: "user" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setDevices((prev) =>
        prev.map((d) =>
          d.id === deviceId
            ? {
                ...d,
                desired_state: desiredState,
                current_state: desiredState,
                current_value: value,
              }
            : d
        )
      );
      return json.data;
    } catch (err) {
      console.error(`Failed to control device ${deviceId}:`, err);
      throw err;
    }
  };

  return {
    connected,
    devices,
    telemetry,
    visionLogs,
    controlActuator,
    refreshData: fetchInitialData,
  };
}
