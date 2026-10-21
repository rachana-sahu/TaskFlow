import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const apiProxy = loadEnv(mode, ".", "VITE_").VITE_API_PROXY_TARGET || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": apiProxy,
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/testSetup.ts",
    },
  };
});
