import path from "node:path"
import base from "./vite.config"

export default {
  ...base,
  build: {
    outDir: "dist/benchmark",
    emptyOutDir: true,
    rolldownOptions: { input: path.resolve(import.meta.dirname, "benchmarks/diff-viewer.html") },
  },
}
