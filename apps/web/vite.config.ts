import react from "@vitejs/plugin-react";
// defineConfig from vitest/config so the `test` block is typed.
import { defineConfig } from "vitest/config";

// GitLab project Pages are served from https://<group>.gitlab.io/<project>/,
// so the base path has to match. CI sets VITE_BASE_PATH to "/$CI_PROJECT_NAME/";
// local development and user/group Pages sites use "/".
const base = process.env.VITE_BASE_PATH ?? "/";

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
