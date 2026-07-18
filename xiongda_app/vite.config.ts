import type { IncomingMessage, ServerResponse } from "http";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

/**
 * Unity WebGL（尤其 2018）依赖 *.unityweb 以二进制方式下载；部分环境下会被当成 text 导致 WASM 初始化失败。
 */
function webglMimePlugin(): Plugin {
  const patch = (_req: IncomingMessage, res: ServerResponse) => {
    const raw = _req.url?.split("?")[0] ?? "";
    if (!raw.includes("/webgl/") && !raw.includes("/webgl-map/")) return;
    if (raw.endsWith(".unityweb") || raw.endsWith(".json")) {
      if (raw.endsWith(".json")) {
        res.setHeader("Content-Type", "application/json; charset=utf-8");
      } else {
        res.setHeader("Content-Type", "application/octet-stream");
      }
    }
  };

  return {
    name: "webgl-mime",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        patch(req, res as ServerResponse);
        next();
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        patch(req, res as ServerResponse);
        next();
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_BEAR_AGENT_PROXY_TARGET?.trim() || "http://127.0.0.1:8765";
  const useAgentProxy = env.VITE_BEAR_AGENT_USE_PROXY === "1" || env.VITE_BEAR_AGENT_USE_PROXY?.toLowerCase() === "true";

  /** 板端 NPU 手部关键点（经 board_bridge :8770），不是 MediaPipe */
  const gestureProxy = {
    "/gesture-api": {
      target: "http://127.0.0.1:8770",
      changeOrigin: true,
      rewrite: (p: string) => p.replace(/^\/gesture-api/, ""),
    },
  };

  return {
    plugins: [react(), webglMimePlugin()],
    server: {
      // 允许板子浏览器通过 PC IP 访问（HDMI 扩展屏 kiosk）
      host: true,
      port: 5173,
      strictPort: true,
      proxy: useAgentProxy
        ? {
            "/api": { target: proxyTarget, changeOrigin: true },
            "/health": { target: proxyTarget, changeOrigin: true },
            ...gestureProxy,
          }
        : { ...gestureProxy },
    },
    // 发布版预览（4173）同样允许局域网访问，并代理摄像头预览
    preview: {
      host: true,
      port: 4173,
      strictPort: true,
      proxy: { ...gestureProxy },
    },
  };
});
