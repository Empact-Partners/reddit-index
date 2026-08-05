import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, include: ["tests/**/*.test.tsx"] },
  resolve: {
    alias: {
      "next/font/local": path.resolve(import.meta.dirname, "tests/mocks/next-font-local.ts"),
      "@": path.resolve(import.meta.dirname),
    },
  },
});
