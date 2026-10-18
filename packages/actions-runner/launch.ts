#!/usr/local/bin/bun
// One Bun invocation owns the job, its deadline, state export and completion callback.
import { spawn } from "node:child_process"
import { appendFileSync } from "node:fs"
import { mkdir, readFile, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { setTimeout as delay } from "node:timers/promises"
import { inflateSync } from "node:zlib"
import { execute } from "./runner.ts"
import type { JobInput, JobResult, LogEntry } from "./types.ts"

const MAX_STATE_BYTES = 32 * 1024 * 1024

async function archive(args: string[], signal: AbortSignal) {
  const child = spawn("tar", args, { stdio: ["ignore", "ignore", "pipe"], signal })
  const errors: Buffer[] = []
  child.stderr.on("data", (chunk: Buffer) => errors.push(chunk))
  const code = await new Promise<number | null>((resolve, reject) => {
    child.once("error", reject)
    child.once("close", resolve)
  })
  if (code !== 0) throw new Error(`State archive failed: ${Buffer.concat(errors).toString()}`)
}

export async function launch(
  input: JobInput,
  {
    root = "/gitedge",
    restoreUrl,
    actionRoot,
    signal,
  }: { root?: string; restoreUrl?: string; actionRoot?: string; signal?: AbortSignal } = {},
) {
  const state = join(root, "state")
  const controller = new AbortController()
  const deadline = setTimeout(
    () => controller.abort(new Error("Job timed out")),
    (input.timeout_seconds || 1200) * 1000,
  )
  const jobSignal = signal ? AbortSignal.any([controller.signal, signal]) : controller.signal
  let result: JobResult = { status: "failure", steps: {}, outputs: {} }
  let code = 1
  await mkdir(join(state, "cache"), { recursive: true })
  await mkdir(join(state, "artifacts"), { recursive: true })
  const log = (entry: LogEntry) =>
    appendFileSync(join(root, "log.jsonl"), `${JSON.stringify(entry)}\n`, { mode: 0o600 })
  const restoreState = async () => {
    if (restoreUrl) {
      const restoreSignal = AbortSignal.any([jobSignal, AbortSignal.timeout(15000)])
      const response = await fetch(restoreUrl, { signal: restoreSignal })
      if (!response.ok) throw new Error(`State restore failed: HTTP ${response.status}`)
      const chunks: Uint8Array[] = []
      if (!response.body) throw new Error("Missing state response body")
      let size = 0
      for await (const chunk of response.body) {
        size += chunk.length
        if (size > MAX_STATE_BYTES) throw new Error("State archive exceeds the 32 MiB limit")
        chunks.push(chunk)
      }
      const path = join(root, "restore.tar.gz")
      await writeFile(path, Buffer.concat(chunks), { mode: 0o600 })
      await archive(["--no-same-owner", "-xzf", path, "-C", state], restoreSignal)
    }
  }
  try {
    result = await execute(input, { root, actionRoot, signal: jobSignal, log, restoreState })
    code = ["success", "skipped"].includes(result.status) ? 0 : 1
  } catch (cause) {
    const error = cause as Error
    result.error = jobSignal.aborted ? "Job timed out or cancelled" : error.message
    log({ msg: result.error })
  } finally {
    clearTimeout(deadline)
    if (controller.signal.aborted) {
      code = 124
      result = { ...result, status: "failure", error: "Job exceeded timeout-minutes" }
    }
    // Collection has its own bounded grace period after the job deadline.
    try {
      const exportSignal = AbortSignal.timeout(15000)
      await archive(["-czf", join(root, "state.tar.gz"), "-C", state, "cache", "artifacts"], exportSignal)
      await archive(["-czf", join(root, "cache.tar.gz"), "-C", state, "cache"], exportSignal)
    } catch (cause) {
      const error = cause as Error
      code = 1
      result = { ...result, status: "failure", error: error.message }
      log({ msg: error.message })
    }
    await writeFile(join(root, "result.json"), JSON.stringify(result), { mode: 0o600 })
    // The controller only collects once this marker is visible.
    await writeFile(join(root, "exit-code"), String(code), { mode: 0o600 })
    if (input.complete_url) {
      const callbackSignal = AbortSignal.timeout(10000)
      for (let attempt = 0; attempt < 4 && !callbackSignal.aborted; attempt++) {
        try {
          const response = await fetch(input.complete_url, { method: "POST", signal: callbackSignal })
          await response.body?.cancel()
          if (response.ok) break
        } catch (cause) {
          const error = cause as Error
          if (callbackSignal.aborted) break
          log({ msg: `Completion delivery failed: ${error.name}` })
        }
        await delay(250 * (attempt + 1))
      }
    }
  }
  return { code, result }
}

async function main() {
  process.umask(0o077)
  const root = process.env.GITEDGE_JOB_ROOT || "/gitedge"
  const encoded = process.env.GITEDGE_JOB
  const descriptor = encoded
    ? process.env.GITEDGE_JOB_ENCODING === "deflate"
      ? inflateSync(Buffer.from(encoded, "base64"), { maxOutputLength: MAX_STATE_BYTES }).toString()
      : encoded
    : await readFile("/gitedge/job.json", "utf8")
  if (!encoded) await rm("/gitedge/job.json")
  const input = JSON.parse(descriptor) as JobInput
  const restoreUrl = process.env.GITEDGE_RESTORE_URL || input.restore_url
  delete process.env.GITEDGE_JOB
  delete process.env.GITEDGE_JOB_ENCODING
  delete process.env.GITEDGE_RESTORE_URL
  delete process.env.GITEDGE_JOB_ROOT
  const controller = new AbortController()
  process.once("SIGTERM", () => controller.abort())
  process.once("SIGINT", () => controller.abort())
  const { code } = await launch(input, { root, restoreUrl, signal: controller.signal })
  process.exitCode = code
}

if (import.meta.main) void main()
