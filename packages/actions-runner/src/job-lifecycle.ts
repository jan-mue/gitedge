import { mkdir } from "node:fs/promises"
import { join } from "node:path"
import { errorMessage, type JobInput, type JobResult, jobSchema } from "./domain/job.ts"
import { writeFile } from "./runtime/files.ts"
import { FileLog } from "./runtime/logger.ts"
import { ArtifactState } from "./storage/artifact-state.ts"
import type { CacheClient } from "./storage/cache-client.ts"
import { WorkflowRunner } from "./workflow-runner.ts"

export interface LaunchOptions {
  root?: string
  actionRoot?: string
  restoreUrl?: string
  signal?: AbortSignal
  cache?: CacheClient
}
export async function launch(
  descriptor: JobInput,
  options: LaunchOptions = {},
): Promise<{ code: number; result: JobResult }> {
  const input = jobSchema.parse(descriptor),
    root = options.root || "/gitedge"
  await mkdir(root, { recursive: true })
  const log = new FileLog(join(root, "log.jsonl"))
  const timeout = new AbortController(),
    timer = setTimeout(() => timeout.abort(new Error("Job exceeded timeout-minutes")), input.timeout_seconds * 1000)
  const signal = options.signal ? AbortSignal.any([timeout.signal, options.signal]) : timeout.signal
  const state = new ArtifactState(root, options.restoreUrl || input.restore_url, signal)
  let result: JobResult = { status: "failure", steps: {}, outputs: {} },
    code = 1
  try {
    result = await new WorkflowRunner(input, {
      root,
      actions: options.actionRoot,
      signal,
      log,
      cache: options.cache,
      restoreArtifacts: () => state.restore(),
    }).run()
    code = result.status === "success" || result.status === "skipped" ? 0 : 1
  } catch (error) {
    result = {
      ...result,
      status: signal.aborted ? "cancelled" : "failure",
      error: signal.aborted ? "Job timed out or cancelled" : errorMessage(error),
    }
    log.write({ msg: result.error || "Job failed" })
  } finally {
    clearTimeout(timer)
    if (timeout.signal.aborted) {
      code = 124
      result = { ...result, status: "failure", error: "Job exceeded timeout-minutes" }
    }
    try {
      await state.export()
    } catch (error) {
      code = 1
      result = { ...result, status: "failure", error: errorMessage(error) }
      log.write({ msg: result.error || "Artifact export failed" })
    }
    await writeFile(join(root, "result.json"), JSON.stringify(result))
    await log.flush()
    await writeFile(join(root, "exit-code"), String(code))
    if (input.complete_url) await deliverCompletion(input.complete_url, log)
    await log.close()
  }
  return { code, result }
}

async function deliverCompletion(url: string, log: FileLog): Promise<void> {
  const signal = AbortSignal.timeout(10000)
  for (let attempt = 0; attempt < 4 && !signal.aborted; attempt++) {
    try {
      const response = await fetch(url, { method: "POST", signal })
      await response.body?.cancel()
      if (response.ok) return
    } catch (error) {
      if (signal.aborted) return
      log.write({ msg: `Completion delivery failed: ${error instanceof Error ? error.name : "NetworkError"}` })
    }
    await Bun.sleep(250 * (attempt + 1))
  }
}
