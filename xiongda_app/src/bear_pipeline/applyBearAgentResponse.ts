import type { AgentContext } from "../services/agentContext";
import type { BearAgentProcessTestResponse } from "./bearAgentTypes";
import { handleBearAgentPayload } from "./handleBearAgentPayload";

/** 与 handleBearAgentPayload 相同，便于旧代码调用 */
export function applyBearAgentResponse(data: BearAgentProcessTestResponse, ctx: AgentContext): void {
  handleBearAgentPayload(data, ctx);
}
