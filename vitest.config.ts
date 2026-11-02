import { defineConfig } from "vitest/config"

export default defineConfig({
  root: import.meta.dirname,
  test: {
    projects: ["frontend/vitest.config.ts", "packages/*/vitest.config.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov", "html"],
      reportsDirectory: "frontend/coverage",
      include: ["**/src/**/*.{ts,tsx}"],
      exclude: [
        "**/*.test.{ts,tsx}",
        "**/src/test/**",
        "**/src/main.tsx",
        "**/src/vite-env.d.ts",
        "**/src/routeTree.gen.ts",
        "**/src/client/**",
      ],
    },
  },
})
