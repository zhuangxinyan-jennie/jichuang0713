import { markMapUnityFullyReady, setMapUnityInstance } from "../services/unityMapBridge";
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

export type UnityWebGLLoadOptions = {
  /** public 下目录，默认 /webgl（熊大）；地图用 /webgl-map */
  basePath?: string;
  /** 加载成功后注册实例；默认写入 window.unityInstance */
  onInstanceReady?: (instance: UnityWebGLHandle) => void;
  /** 2018 模板：隐藏此 canvas（熊大页用 unity-canvas） */
  hideCanvasId?: string;
  logTag?: string;
};

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
    mapUnityInstance?: UnityWebGLHandle;
  }
}

function is2018Info(cfg: UnityBuildInfo): cfg is UnityBuildInfo2018 {
  if ("loaderMode" in cfg && cfg.loaderMode === "unity2018") return true;
  if ("unityLoaderUrl" in cfg && "jsonManifest" in cfg && !("loaderUrl" in cfg)) return true;
  return false;
}

/** 最近一次加载失败原因（给界面提示用） */
export let lastUnityLoadError: string | null = null;
export let lastMapUnityLoadError: string | null = null;

const unityBootPromises = new Map<string, Promise<boolean>>();

function normalizeBasePath(basePath: string): string {
  const trimmed = basePath.trim().replace(/\/+$/, "");
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
}

/**
 * 若存在 `{basePath}/build-info.json`，则加载 Unity WebGL（支持 **2018 UnityLoader** 与 **2019+ createUnityInstance**）。
 */
export function tryLoadUnityWebGL(
  containerId: string,
  canvasForModern?: HTMLCanvasElement | null,
  options?: UnityWebGLLoadOptions
): Promise<boolean> {
  const basePath = normalizeBasePath(options?.basePath ?? "/webgl");
  const cacheKey = `${basePath}::${containerId}`;
  const existing = unityBootPromises.get(cacheKey);
  if (existing) return existing;

  if (basePath === "/webgl-map") {
    lastMapUnityLoadError = null;
  } else {
    lastUnityLoadError = null;
  }

  const promise = loadUnityWebGLInner(containerId, canvasForModern, basePath, options).then((ok) => {
    const tag = options?.logTag ?? "[Unity]";
    if (!ok) {
      const fallback = "Unity 未就绪（详见控制台日志）";
      if (basePath === "/webgl-map") {
        if (!lastMapUnityLoadError) lastMapUnityLoadError = fallback;
      } else if (!lastUnityLoadError) {
        lastUnityLoadError = fallback;
      }
      console.info(`${tag} 未加载 ${basePath}/build-info.json 或初始化失败`);
    }
    return ok;
  });
  unityBootPromises.set(cacheKey, promise);
  return promise;
}

async function loadUnityWebGLInner(
  containerId: string,
  canvasForModern: HTMLCanvasElement | null | undefined,
  basePath: string,
  options?: UnityWebGLLoadOptions
): Promise<boolean> {
  const tag = options?.logTag ?? "[Unity]";
  const setError = (msg: string) => {
    if (basePath === "/webgl-map") lastMapUnityLoadError = msg;
    else lastUnityLoadError = msg;
  };

  try {
    const res = await fetch(`${basePath}/build-info.json`, { cache: "no-store" });
    if (!res.ok) {
      setError(`缺少或无法访问 ${basePath}/build-info.json（HTTP ${res.status}）`);
      return false;
    }
    const cfg = (await res.json()) as UnityBuildInfo;

    const registerInstance = (instance: UnityWebGLHandle) => {
      if (options?.onInstanceReady) {
        options.onInstanceReady(instance);
      } else {
        setGlobalUnityInstance(instance);
      }
    };

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
        setError(`找不到挂载节点 #${containerId}`);
        console.error(`${tag} 找不到容器 #${containerId}`);
        return false;
      }
      const hideCanvasId = options?.hideCanvasId;
      if (hideCanvasId) {
        const reactCanvas = document.getElementById(hideCanvasId) as HTMLCanvasElement | null;
        if (reactCanvas) reactCanvas.style.display = "none";
      }

      el.innerHTML = "";

      const UL = window.UnityLoader;
      if (!UL?.instantiate) {
        setError("UnityLoader.instantiate 不存在（UnityLoader.js 是否加载失败？）");
        return false;
      }
      const gameInstance = UL.instantiate(containerId, cfg.jsonManifest, {
        onProgress: (gi: unknown, p: number) => {
          if (typeof window.UnityProgress === "function") {
            window.UnityProgress(gi, p);
          }
          if (p >= 0.99 && basePath === "/webgl-map") {
            markMapUnityFullyReady();
          }
        },
      });
      registerInstance(gameInstance as UnityWebGLHandle);
      console.info(`${tag} 2018 UnityLoader 已启动 (${basePath})`);
      if (basePath === "/webgl-map") {
        window.setTimeout(() => markMapUnityFullyReady(), 2500);
      }
      return true;
    }

    const m = cfg as UnityBuildInfoModern;
    if (!m.loaderUrl || !m.dataUrl || !m.frameworkUrl || !m.codeUrl) {
      setError("build-info.json 缺少 modern 四地址");
      return false;
    }
    const canvas = canvasForModern ?? (document.getElementById("unity-canvas") as HTMLCanvasElement | null);
    if (!canvas) {
      setError("现代模板需要 canvas 元素");
      return false;
    }
    canvas.style.display = "";

    await injectScript(m.loaderUrl);
    const create = window.createUnityInstance;
    if (typeof create !== "function") {
      setError("未找到 createUnityInstance");
      return false;
    }
    const streamingBase = m.streamingAssetsUrl ?? `${basePath}/StreamingAssets`;
    const instance = await create(
      canvas,
      {
        dataUrl: m.dataUrl,
        frameworkUrl: m.frameworkUrl,
        codeUrl: m.codeUrl,
        streamingAssetsUrl: streamingBase,
      },
      () => {}
    );
    registerInstance(instance);
    console.info(`${tag} 现代 WebGL 已加载 (${basePath})`);
    return true;
  } catch (e) {
    setError(e instanceof Error ? e.message : String(e));
    console.warn(`${tag} 加载失败`, e);
    return false;
  }
}
