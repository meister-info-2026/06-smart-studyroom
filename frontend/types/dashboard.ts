export interface DeviceItem {
  id: string;
  name: string;
  kind: string;
  desired_state?: string | null;
  current_state?: string | null;
  desired_value?: unknown;
  current_value?: unknown;
  updated_at?: string | null;
  created_at?: string | null;
}

export interface SeatTelemetry {
  seat_id: string;
  is_occupied: boolean;
  drowsiness_count: number;
  posture_warning_count: number;
  posture_status: "GOOD" | "TURTLE_NECK" | "UNKNOWN" | string;
  study_time_seconds: number;
  led_brightness: number;
}

export interface VisionEventLog {
  id?: number;
  event_type: string;
  detected: boolean;
  count?: number;
  confidence?: number | null;
  created_at?: string;
}

export interface SessionReport {
  session_id: string;
  seat_id: string;
  total_study_seconds: number;
  study_time_formatted: string;
  drowsiness_count: number;
  posture_warning_count: number;
  focus_score: number;
  checked_out_at: string;
  report_url: string;
  qr_payload: string;
}
