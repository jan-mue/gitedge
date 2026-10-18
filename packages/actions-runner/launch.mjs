#!/usr/local/bin/bun
// One Bun invocation owns the job, its deadline, state export and completion callback.
import { appendFileSync } from "node:fs"
import { mkdir, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { execute } from "./runner.mjs"

const MAX_STATE_BYTES = 32 * 1024 * 1024

async function archive(args, signal) {
  const child = Bun.spawn(["tar", ...args], { stdout: "ignore", stderr: "pipe", signal })
  const [code, error] = await Promise.all([child.exited, new Response(child.stderr).text()])
  if (code !== 0) throw new Error(`State archive failed: ${error}`)
}

export async function launch(input, { root = "/gitedge", restoreUrl, actionRoot, signal } = {}) {
  const state = join(root, "state")
  const controller = new AbortController()
  const deadline = setTimeout(() => controller.abort(new Error("Job timed out")), input.timeout_seconds * 1000)
  const jobSignal = signal ? AbortSignal.any([controller.signal, signal]) : controller.signal
  let result = { status: "failure", steps: {}, outputs: {} }
  let code = 1
  await mkdir(join(state, "cache"), { recursive: true })
  await mkdir(join(state, "artifacts"), { recursive: true })
  await writeFile(join(root, "input.json"), JSON.stringify(input), { mode: 0o600 })
  const log = (entry) => appendFileSync(join(root, "log.jsonl"), `${JSON.stringify(entry)}\n`, { mode: 0o600 })
  try {
    if (restoreUrl) {
      const response = await fetch(restoreUrl, { signal: jobSignal })
      if (!response.ok) throw new Error(`State restore failed: HTTP ${response.status}`)
      const chunks = []
      let size = 0
      for await (const chunk of response.body) {
        size += chunk.length
        if (size > MAX_STATE_BYTES) throw new Error("State archive exceeds the 32 MiB limit")
        chunks.push(chunk)
      }
      const path = join(root, "restore.tar.gz")
      await writeFile(path, Buffer.concat(chunks), { mode: 0o600 })
      await archive(["--no-same-owner", "-xzf", path, "-C", state], jobSignal)
    }
    result = await execute(input, { root, actionRoot, signal: jobSignal, log })
    code = ["success", "skipped"].includes(result.status) ? 0 : 1
  } catch (error) {
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
    } catch (error) {
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
        } catch (error) {
          if (callbackSignal.aborted) break
          log({ msg: `Completion delivery failed: ${error.name}` })
        }
        await Bun.sleep(250 * (attempt + 1))
      }
    }
  }
  return { code, result }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.umask(0o077)
  const input = JSON.parse(process.env.GITEDGE_JOB)
  const restoreUrl = process.env.GITEDGE_RESTORE_URL
  delete process.env.GITEDGE_JOB
  delete process.env.GITEDGE_RESTORE_URL
  const controller = new AbortController()
  process.once("SIGTERM", () => controller.abort())
  process.once("SIGINT", () => controller.abort())
  const { code } = await launch(input, { restoreUrl, signal: controller.signal })
  process.exitCode = code
}
