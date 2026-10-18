// Run inside a disposable prepared sandbox. Measures fresh Bun processes, not VM provisioning.
import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { createServer } from "node:http"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import type { JobInput } from "./types.ts"

const samples = Number(process.env.GITEDGE_BENCHMARK_SAMPLES || 20)
assert.ok(Number.isInteger(samples) && samples > 0 && samples <= 100)
const entries = process.argv.slice(2).map((entry) => {
  const separator = entry.indexOf("=")
  assert.ok(separator > 0, "Expected label=/absolute/path/to/launcher")
  return { label: entry.slice(0, separator), entry: resolve(entry.slice(separator + 1)) }
})
assert.ok(entries.length, "Supply at least one label=launcher argument")
const tar = Bun.spawn(["tar", "-czf", "-", "--files-from", "/dev/null"], { stdout: "pipe", stderr: "pipe" })
const archive = Buffer.from(await new Response(tar.stdout).arrayBuffer())
assert.equal(await tar.exited, 0)
let requests = 0
const server = createServer((_request, response) => {
  requests++
  setTimeout(() => response.end(archive), 100)
})
await new Promise<void>((done) => server.listen(0, "127.0.0.1", done))
const address = server.address()
assert.ok(address && typeof address !== "string")
interface Sample {
  first_step_ms: number
  first_process_ms: number
  total_ms: number
  state_requests: number
}
const results: Record<string, Sample[]> = {}
try {
  // Interleave variants to reduce order and filesystem-cache bias. No runner process is reused.
  for (let iteration = 0; iteration < samples; iteration++) {
    for (const { label, entry } of entries) {
      for (const restore of [false, true]) {
        const root = await mkdtemp(join(tmpdir(), "gitedge-startup-"))
        const beforeRequests = requests
        const started = Date.now()
        const input: JobInput = {
          workflow: `defaults:
  run:
    shell: bun {0}
jobs:
  benchmark:
    steps:
      - run: |
          import { writeFileSync } from "node:fs"
          writeFileSync(process.env.BENCHMARK_MARKER, String(Date.now()))
`,
          job: "benchmark",
          dispatched_at_ms: started,
          timeout_seconds: 10,
          env: { GITHUB_RUN_ID: "1", BENCHMARK_MARKER: join(root, "first-process-ms") },
          ...(restore ? { restore_url: `http://127.0.0.1:${address.port}` } : {}),
        }
        try {
          const child: Bun.Subprocess<"ignore", "ignore", "pipe"> = Bun.spawn([process.execPath, entry], {
            env: { ...process.env, GITEDGE_JOB: JSON.stringify(input), GITEDGE_JOB_ROOT: root },
            stdout: "ignore",
            stderr: "pipe",
          })
          const errors: string = await new Response(child.stderr).text()
          assert.equal(await child.exited, 0, errors)
          const total = Date.now() - started
          const result = JSON.parse(await readFile(join(root, "result.json"), "utf8"))
          assert.equal(result.status, "success")
          const key = `${label}/${restore ? "100ms-state-endpoint" : "no-state-endpoint"}`
          results[key] ??= []
          results[key].push({
            first_step_ms: result.startup_ms,
            first_process_ms: Number(await readFile(join(root, "first-process-ms"), "utf8")) - started,
            total_ms: total,
            state_requests: requests - beforeRequests,
          })
        } finally {
          await rm(root, { recursive: true, force: true })
        }
      }
    }
  }
  const summary = Object.fromEntries(
    Object.entries(results).map(([label, values]) => [
      label,
      {
        samples: values.length,
        ...Object.fromEntries(
          (["first_step_ms", "first_process_ms", "total_ms"] as const).map((metric) => {
            const sorted = values.map((value) => value[metric]).sort((a, b) => a - b)
            return [metric, { min: sorted[0], median: sorted[Math.floor(sorted.length / 2)], max: sorted.at(-1) }]
          }),
        ),
        state_requests: values.reduce((sum, value) => sum + value.state_requests, 0),
      },
    ]),
  )
  console.log(JSON.stringify({ runtime: process.version, bun: Bun.version, summary, results }))
} finally {
  await new Promise<void>((done) => server.close(() => done()))
}
