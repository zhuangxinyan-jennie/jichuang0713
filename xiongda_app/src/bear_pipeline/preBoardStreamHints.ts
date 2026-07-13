/**
 * 与精简包 pre_on_board（board_deploy）一致的端口与通道说明，仅供前端联调提示。
 * 板端推理后会主动连接 **运行 sender 的这台 PC** 的 18082（画面：JSON 帧头 + JPEG）、18083（ASR：JSON 消息流）。
 * @see pre_on_board board_deploy/pc_result_viewer.py / pc_asr_result_viewer.py / pc_*_sender.py
 */
export const PRE_BOARD_STREAM_PORTS = {
  /** PC → 板：视频编码流 */
  videoToBoard: 18080,
  /** PC → 板：麦克风流 */
  audioToBoard: 18081,
  /** 板 → PC：画面结果（与 pc_result_viewer 默认端口一致） */
  visionFromBoard: 18082,
  /** 板 → PC：语音识别推送（与 pc_asr_result_viewer 默认端口一致） */
  asrFromBoard: 18083,
} as const;

export function preBoardStreamHintParagraph(): string {
  const p = PRE_BOARD_STREAM_PORTS;
  return (
    `板端回连本机 TCP ${p.visionFromBoard}（画面 meta+JPEG）、${p.asrFromBoard}（ASR JSON）；` +
    `PC 发往板端 ${p.videoToBoard}/${p.audioToBoard}。` +
    ` OpenCV 预览（run_all 默认）与 bear_agent board_bridge 不能同时占 ${p.visionFromBoard}/${p.asrFromBoard}，需使用 run_all --bear-bridge 或仅跑 board_bridge。`
  );
}
