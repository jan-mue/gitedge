import { mkdir } from "node:fs/promises"
import { join } from "node:path"
import { errorMessage, type JobInput, type JobResult, jobSchema } from "./domain/job.ts"
import { writeFile } from "./runtime/files.ts"
import { JobLog, JobLogger } from "./runtime/logger.ts"
import { JobReporter } from "./runtime/reporter.ts"
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
  const input = jobSchema.parse(descriptor)
  const root = options.root || "/gitedge"
  await mkdir(root, { recursive: true })
  const reporter = new JobReporter(input)
  const log = new JobLog(root, input.attempt, reporter)
  const logger = new JobLogger(log, [...Object.values(input.secrets), input.report_token || ""])
  const timeout = new AbortController()
  const timer = setTimeout(() => timeout.abort(new Error("Job exceeded timeout-minutes")), input.timeout_seconds * 1000)
  const signal = options.signal ? AbortSignal.any([timeout.signal, options.signal]) : timeout.signal
  const state = new ArtifactState(root, options.restoreUrl || input.restore_url, signal)
  let result: JobResult = { status: "failure", steps: {}, outputs: {} }
  let code = 1
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
    await logger.emit(result.error || "Job failed")
  } finally {
    clearTimeout(timer)
    if (timeout.signal.aborted) {
      code = 124
      result = { ...result, status: "failure", error: "Job exceeded timeout-minutes" }
    }
    try {
      await state.export()
      if (reporter.enabled) {
        const response = await reporter.post("artifacts", Bun.file(join(root, "state.tar.gz")))
        await response?.body?.cancel()
      }
    } catch (error) {
      code = 1
      result = { ...result, status: "failure", error: errorMessage(error) }
      await logger.emit(result.error || "Artifact export failed")
    }
    if (!reporter.enabled) {
      await writeFile(join(root, "result.json"), JSON.stringify({ ...result, attempt: input.attempt }))
      await writeFile(join(root, "exit-code"), String(code))
    }
    await log.close()
    const response = await reporter.post(
      "complete",
      JSON.stringify({
        version: 1,
        ...input.attempt,
        exit_code: code,
        last_seq: log.lastSequence,
        result,
      }),
    )
    await response?.body?.cancel()
  }
  return { code, result }
}
