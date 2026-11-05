import { defineProject } from "vitest/config"

export default defineProject({
  root: import.meta.dirname,
  test: { name: "actions-compiler", environment: "node", testTimeout: 10000 },
})
