import type { Dispatch, SetStateAction } from "react";

export type AgentContext = {
  setCurrentSmplPath: Dispatch<SetStateAction<string>>;
  setSubtitle: Dispatch<SetStateAction<string>>;
};

export function makeAgentContext(
  setCurrentSmplPath: Dispatch<SetStateAction<string>>,
  setSubtitle: Dispatch<SetStateAction<string>>
): AgentContext {
  return { setCurrentSmplPath, setSubtitle };
}
