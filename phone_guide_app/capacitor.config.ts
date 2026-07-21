import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.fudan.phoneguide",
  appName: "Phone Guide",
  webDir: "dist/build/h5",
  android: {
    allowMixedContent: true,
  },
};

export default config;
