/**
 * 设为 true 时展示端口、API、board_bridge 等开发者说明。
 * 面向游客的演示环境保持默认关闭。
 */
export const agentPipelineDebugUi = import.meta.env.VITE_AGENT_PIPELINE_DEBUG_UI === "true";
