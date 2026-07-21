export type SafetyStateName =
  | "NORMAL"
  | "WARNING"
  | "SAFETY_ALERT"
  | "RECOVERY"
  | "MONITOR_FAULT";

export type SafetyState = {
  state: SafetyStateName;
  crowd_state: "NORMAL" | "WARNING" | "CRITICAL";
  monitor_fault: boolean;
  locked: boolean;
  alert_id: number;
  alert_started_at: number | null;
  resume_cache_expired: boolean;
  demo_active: boolean;
  source: string;
  last_sample_at: number | null;
  last_sample_seq: number | null;
  critical_samples: number;
  recovery_samples: number;
  transition_seq: number;
  event: string | null;
  event_seq: number | null;
};

export const INITIAL_SAFETY_STATE: SafetyState = {
  state: "NORMAL",
  crowd_state: "NORMAL",
  monitor_fault: false,
  locked: false,
  alert_id: 0,
  alert_started_at: null,
  resume_cache_expired: false,
  demo_active: false,
  source: "live",
  last_sample_at: null,
  last_sample_seq: null,
  critical_samples: 0,
  recovery_samples: 0,
  transition_seq: 0,
  event: null,
  event_seq: null,
};

