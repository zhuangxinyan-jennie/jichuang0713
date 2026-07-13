import { setGlobalUnityInstance, type UnityWebGLHandle } from "../services/unitySendClip";

/** 2019+ 现代模板：createUnityInstance + 四个资源 URL */
export type UnityBuildInfoModern = {
  loaderMode?: "modern" | "unity2018";
  loaderUrl: string;
  dataUrl: string;
  frameworkUrl: string;
  codeUrl: string;
  streamingAssetsUrl?: string;
};

/** Unity 2018 模板：UnityLoader.instantiate + webgl.json */
export type UnityBuildInfo2018 = {
  loaderMode: "unity2018";
  unityLoaderUrl: string;
  unityProgressUrl: string;
  /** 可选，加载条 / 启动画面样式 */
  templateStyleUrl?: string;
  jsonManifest: string;
  streamingAssetsUrl?: string;
};

export type UnityBuildInfo = (UnityBuildInfoModern | UnityBuildInfo2018) & { loaderMode?: string };

function injectLinkStylesheet(href: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`link[href="${href}"]`)) {
      resolve();
      return;
    }
    const l = document.createElement("link");
    l.rel = "stylesheet";
    l.type = "text/css";
    l.href = href;
    l.onload = () => resolve();
    l.onerror = () => reject(new Error(`无法加载样式 ${href}`));
    document.head.appendChild(l);
  });
}

function injectScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`无法加载 ${src}`));
    document.body.appendChild(s);
  });
}

declare global {
  interface Window {
    createUnityInstance?: (
      canvas: HTMLCanvasElement,
      config: Record<string, string>,
      progress: (p: number) => void
    ) => Promise<UnityWebGLHandle>;
    /** Unity 2018 WebGL */
    UnityLoader?: {
      instantiate: (
        id: string,
        jsonPath: string,
        opts: { onProgress: (unityInstance: UnityWebGLHandle, progress: number) => void }
      ) => UnityWebGLHandle;
    };
    UnityProgress?: (unityInstance: unknown, progress: number) => void;
  }
}

function is2018Info(cfg: UnityBuildInfo): cfg is UnityBuildInfo2018 {
  if ("loaderMode" in cfg && cfg.loaderMode === "unity2018") return true;
  if ("unityLoaderUrl" in cfg && "jsonManifest" in cfg && !("loaderUrl" in cfg)) return true;
  return false;
}

/** 最近一次加载失败原因（给界面提示用） */
export let lastUnityLoadError: string | null = null;

/**
 * React 18 StrictMode 会重复执行 effect，若两次都清空 #unity-game-mount 会打断 Unity 初始化。
 * 使用单次 Promise，全页只启动一轮加载。
 */
let unityBootPromise: Promise<boolean> | null = null;

/**
 * 若存在 `public/webgl/build-info.json`，则加载 Unity WebGL（支持 **2018 UnityLoader** 与 **2019+ createUnityInstance**）。
 */
export function tryLoadUnityWebGL(
  containerId: string,
  canvasForModern?: HTMLCanvasElement | null
): Promise<boolean> {
  if (unityBootPromise) return unityBootPromise;
  lastUnityLoadError = null;
  unityBootPromise = loadUnityWebGLInner(containerId, canvasForModern).then((ok) => {
    if (!ok && !lastUnityLoadError) {
      lastUnityLoadError = "Unity 未就绪（详见控制台 [Unity] 日志）";
    }
    return ok;
  });
  return unityBootPromise;
}

async function loadUnityWebGLInner(
  containerId: string,
  canvasForModern?: HTMLCanvasElement | null
): Promise<boolean> {
  try {
    const res = await fetch("/webgl/build-info.json", { cache: "no-store" });
    if (!res.ok) {
      lastUnityLoadError = `缺少或无法访问 /webgl/build-info.json（HTTP ${res.status}）`;
      console.info("[Unity] 未找到 /webgl/build-info.json，跳过自动加载（见 public/webgl/说明.txt）");
      return false;
    }
    const cfg = (await res.json()) as UnityBuildInfo;

    if (is2018Info(cfg)) {
      if (cfg.templateStyleUrl) {
        try {
          await injectLinkStylesheet(cfg.templateStyleUrl);
        } catch {
          /* 样式缺失不阻断 */
        }
      }
      if (cfg.unityProgressUrl) {
        await injectScript(cfg.unityProgressUrl);
      }
      await injectScript(cfg.unityLoaderUrl);

      const el = document.getElementById(containerId);
      if (!el) {
        lastUnityLoadError = `找不到挂载节点 #${containerId}`;
        console.error("[Unity] 找不到容器 #" + containerId);
        return false;
      }
      const reactCanvas = document.getElementById("unity-canvas") as HTMLCanvasElement | null;
      if (reactCanvas) reactCanvas.style.display = "none";

      // 2018 只在专用挂载点内清空，避免拆掉整块 React 布局
      el.innerHTML = "";

      const UL = window.UnityLoader;
      if (!UL?.instantiate) {
        lastUnityLoadError = "UnityLoader.instantiate 不存在（UnityLoader.js 是否加载失败？）";
        console.error("[Unity] UnityLoader.instantiate 不存在，请检查 UnityLoader.js");
        return false;
      }
      const gameInstance = UL.instantiate(containerId, cfg.jsonManifest, {
        onProgress: (gi: unknown, p: number) => {
          if (typeof window.UnityProgress === "function") {
            window.UnityProgress(gi, p);
          }
        },
      });
      setGlobalUnityInstance(gameInstance as UnityWebGLHandle);
      console.info("[Unity] 2018 UnityLoader 已启动，可 SendMessage");
      return true;
    }

    const m = cfg as UnityBuildInfoModern;
    if (!m.loaderUrl || !m.dataUrl || !m.frameworkUrl || !m.codeUrl) {
      lastUnityLoadError = "build-info.json 缺少 modern 四地址（loaderUrl/dataUrl/frameworkUrl/codeUrl）";
      console.warn("[Unity] build-info.json 缺少 modern 四地址");
      return false;
    }
    const canvas = canvasForModern ?? (document.getElementById("unity-canvas") as HTMLCanvasElement | null);
    if (!canvas) {
      lastUnityLoadError = "现代模板需要页面中存在 #unity-canvas";
      console.error("[Unity] 现代模板需要 <canvas id=\"unity-canvas\" />");
      return false;
    }
    canvas.style.display = "";

    await injectScript(m.loaderUrl);
    const create = window.createUnityInstance;
    if (typeof create !== "function") {
      lastUnityLoadError = "未找到 createUnityInstance（modern 包是否与配置一致？）";
      console.error("[Unity] 未找到 createUnityInstance，请用 loaderMode: unity2018");
      return false;
    }
    const instance = await create(
      canvas,
      {
        dataUrl: m.dataUrl,
        frameworkUrl: m.frameworkUrl,
        codeUrl: m.codeUrl,
        streamingAssetsUrl: m.streamingAssetsUrl ?? "/webgl/StreamingAssets",
      },
      () => {}
    );
    setGlobalUnityInstance(instance);
    console.info("[Unity] 现代 WebGL 已加载");
    return true;
  } catch (e) {
    lastUnityLoadError = e instanceof Error ? e.message : String(e);
    console.warn("[Unity] 加载失败", e);
    return false;
  }
}
