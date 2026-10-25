import { defineProject } from "vitest/config"

export default defineProject({
  root: import.meta.dirname,
  test: { name: "actions-runner", environment: "node", testTimeout: 10000 },
})
