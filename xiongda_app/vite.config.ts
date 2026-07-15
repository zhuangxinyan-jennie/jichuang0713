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

  /** 本机手势 landmarks（MediaPipe），与熊大 Agent /api 分开，避免端口冲突 */
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
      proxy: useAgentProxy
        ? {
            "/api": { target: proxyTarget, changeOrigin: true },
            "/health": { target: proxyTarget, changeOrigin: true },
            ...gestureProxy,
          }
        : { ...gestureProxy },
    },
  };
});
