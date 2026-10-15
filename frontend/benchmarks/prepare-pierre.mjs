import { spawnSync } from "node:child_process"
import { mkdtemp, readFile, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

// Keep the comparison library out of the application and its dependency graph.
const directory = await mkdtemp(join(tmpdir(), "gitedge-pierre-1.5.2-"))
await writeFile(join(directory, "package.json"), JSON.stringify({ private: true, type: "module" }))
await writeFile(join(directory, "main.js"), await readFile(new URL("./pierre-fixture.js", import.meta.url)))
await writeFile(
  join(directory, "index.html"),
  '<!doctype html><html lang="en"><head><meta charset="UTF-8"></head><body style="margin:24px"><div id="root"></div><script type="module" src="./main.js"></script></body></html>',
)
const installation = spawnSync(
  "bun",
  ["add", "@pierre/diffs@1.5.2", "react@19.3.0", "react-dom@19.3.0", "vite@8.3.4"],
  { cwd: directory, stdio: "inherit" },
)
if (installation.status !== 0) process.exit(installation.status ?? 1)
console.log("Pierre benchmark prepared in:", directory)
console.log("From that directory, run: bunx vite build && bunx vite preview --host 127.0.0.1 --port 5176")
console.log("Then, from frontend/: bun run benchmark:measure http://127.0.0.1:5176/")
