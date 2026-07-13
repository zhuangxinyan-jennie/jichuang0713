import { useEffect, useState } from "react";
import { isUnityInstanceReady } from "../services/unitySendClip";

export function useUnityReady(): boolean {
  const [ready, setReady] = useState(() => isUnityInstanceReady());

  useEffect(() => {
    if (ready) return;
    const t = window.setInterval(() => {
      if (isUnityInstanceReady()) {
        setReady(true);
        window.clearInterval(t);
      }
    }, 400);
    return () => window.clearInterval(t);
  }, [ready]);

  return ready;
}
