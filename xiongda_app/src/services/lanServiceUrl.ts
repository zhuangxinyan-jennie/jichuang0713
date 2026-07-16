/**
 * 页面从板子浏览器打开时，把 127.0.0.1 服务地址改成当前页面主机（PC IP）。
 * 这样 PC 本机调试仍用 127.0.0.1；HDMI 扩展屏打开 http://192.168.137.1:5173 时自动连 PC。
 */
export function rewriteLoopbackServiceUrl(explicitUrl: string | undefined, defaultBase: string): string {
  const fallback = (explicitUrl || defaultBase).trim().replace(/\/$/, "") || defaultBase;
  if (typeof window === "undefined") {
    return fallback;
  }
  const pageHost = (window.location.hostname || "").trim();
  const pageIsLan = Boolean(pageHost) && pageHost !== "localhost" && pageHost !== "127.0.0.1";
  if (!pageIsLan) {
    return fallback;
  }
  try {
    const u = new URL(fallback);
    if (u.hostname === "localhost" || u.hostname === "127.0.0.1") {
      u.hostname = pageHost;
    }
    return u.origin.replace(/\/$/, "");
  } catch {
    return fallback;
  }
}
