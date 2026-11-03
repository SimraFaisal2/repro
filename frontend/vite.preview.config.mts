// Preview-only Vite config: allows the hostname supplied in PREVIEW_HOST so the
// dashboard can be served from a cloud workspace. The tracked vite.config.ts is
// left untouched.
import { defineConfig, mergeConfig } from "vite";
import base from "./vite.config";

export default defineConfig((env) => {
  const b: any = typeof base === "function" ? (base as any)(env) : base;
  return mergeConfig(b, {
    server: {
      host: "0.0.0.0",
      port: 3000,
      allowedHosts: [process.env.PREVIEW_HOST || "localhost"],
    },
  });
});
