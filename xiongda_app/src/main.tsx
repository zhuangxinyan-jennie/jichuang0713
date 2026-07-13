import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
// 接入 WebGL 后，在此 import createUnityInstance(…)，
// 成功回调中：window.unityInstance = u; 或从 ./services/unitySendClip 调 setGlobalUnityInstance(u);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
