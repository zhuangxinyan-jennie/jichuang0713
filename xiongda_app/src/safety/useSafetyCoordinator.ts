import { useCallback, useEffect, useRef, useState } from "react";
import { SafetyAudioController } from "./safetyAudio";
import {
  fetchSafetyState,
  finishSafetyRecovery,
  releaseSafetyDemo,
  triggerSafetyDemo,
} from "./safetyClient";
import { INITIAL_SAFETY_STATE, type SafetyState } from "./types";

type Options = {
  onEmergencyStop: () => void;
  onRecoveryComplete: (resumeCacheExpired: boolean) => void;
};

export function useSafetyCoordinator({ onEmergencyStop, onRecoveryComplete }: Options) {
  const [safety, setSafety] = useState<SafetyState>(INITIAL_SAFETY_STATE);
  const [connectionError, setConnectionError] = useState("");
  const [demoBusy, setDemoBusy] = useState(false);
  const safetyRef = useRef(safety);
  const audioRef = useRef<SafetyAudioController | null>(null);
  const previousStateRef = useRef(safety.state);
  const lastWarningEventRef = useRef<number | null>(null);
  const recoveryCompletingRef = useRef(false);

  if (audioRef.current === null && typeof window !== "undefined") {
    audioRef.current = new SafetyAudioController();
  }

  const applySafety = useCallback((next: SafetyState) => {
    safetyRef.current = next;
    setSafety(next);
    setConnectionError("");
  }, []);

  useEffect(() => {
    let cancelled = false;
    let running = false;
    const tick = async () => {
      if (running) return;
      running = true;
      try {
        const next = await fetchSafetyState();
        if (!cancelled) applySafety(next);
      } catch (error) {
        if (!cancelled) {
          setConnectionError(error instanceof Error ? error.message : String(error));
        }
      } finally {
        running = false;
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 400);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [applySafety]);

  useEffect(() => {
    const previous = previousStateRef.current;
    previousStateRef.current = safety.state;

    if (safety.state === "SAFETY_ALERT") {
      if (previous !== "SAFETY_ALERT") {
        recoveryCompletingRef.current = false;
        onEmergencyStop();
        audioRef.current?.startCritical();
      }
      return;
    }

    if (safety.state === "RECOVERY") {
      if (previous !== "RECOVERY") {
        onEmergencyStop();
        audioRef.current?.startRecovery(() => {
          if (recoveryCompletingRef.current) return;
          recoveryCompletingRef.current = true;
          const expired = safetyRef.current.resume_cache_expired;
          const finish = async () => {
            if (safetyRef.current.state !== "RECOVERY") {
              recoveryCompletingRef.current = false;
              return;
            }
            try {
              const next = await finishSafetyRecovery();
              applySafety(next);
              if (next.state === "NORMAL") onRecoveryComplete(expired);
            } catch (error) {
              setConnectionError(error instanceof Error ? error.message : String(error));
              window.setTimeout(() => void finish(), 1000);
            }
          };
          void finish();
        });
      }
      return;
    }

    recoveryCompletingRef.current = false;
    if (safety.state === "WARNING" && safety.event === "warning_notify") {
      if (safety.event_seq !== lastWarningEventRef.current) {
        lastWarningEventRef.current = safety.event_seq;
        audioRef.current?.queueWarning(() => safetyRef.current.state === "WARNING");
      }
      return;
    }

    audioRef.current?.cancel();
  }, [
    applySafety,
    onEmergencyStop,
    onRecoveryComplete,
    safety.event,
    safety.event_seq,
    safety.state,
  ]);

  useEffect(() => () => audioRef.current?.cancel(), []);

  const toggleDemo = useCallback(async () => {
    if (demoBusy) return;
    setDemoBusy(true);
    try {
      const next = safetyRef.current.demo_active
        ? await releaseSafetyDemo()
        : await triggerSafetyDemo();
      applySafety(next);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : String(error));
    } finally {
      setDemoBusy(false);
    }
  }, [applySafety, demoBusy]);

  return {
    safety,
    safetyRef,
    connectionError,
    demoBusy,
    toggleDemo,
  };
}
