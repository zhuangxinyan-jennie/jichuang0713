/// <reference types="vite/client" />

declare global {
  interface Window {
    unityInstance?: {
      SendMessage: (objectName: string, methodName: string, value?: string) => void;
    };
  }
}

export {};
