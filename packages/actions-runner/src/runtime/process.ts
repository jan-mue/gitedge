import { join } from "node:path"
import type { Environment } from "../domain/workflow.ts"
import { CommandFiles, OutputCommands } from "./commands.ts"
import type { JobEnvironment } from "./environment.ts"
import type { Workspace } from "./files.ts"
import type { JobLogger } from "./logger.ts"

export interface ProcessRequest {
  command: string
  args: string[]
  environment: Environment
  cwd: string
  step: string
  outputs: Environment
  state: Environment
  signal: AbortSignal
}

export class ProcessExecutor {
  constructor(
    private readonly workspace: Workspace,
    private readonly environment: JobEnvironment,
    private readonly logger: JobLogger,
  ) {}

  async run(request: ProcessRequest): Promise<void> {
    request.signal.throwIfAborted()
    const commands = new CommandFiles(join(this.workspace.temporary, crypto.randomUUID()))
    await commands.prepare()
    const environment = { ...request.environment, ...commands.paths }
    // The artifact toolkit requires a GitHub hostname even with a custom results service.
    if (
      ["actions/upload-artifact", "actions/download-artifact"].includes(environment.GITHUB_ACTION_REPOSITORY || "") &&
      environment.ACTIONS_RESULTS_URL &&
      new URL(environment.ACTIONS_RESULTS_URL).hostname === "127.0.0.1"
    )
      environment.GITHUB_SERVER_URL = "https://github.com"
    const child = Bun.spawn([request.command, ...request.args], {
      cwd: request.cwd,
      env: environment,
      stdin: "ignore",
      stdout: "pipe",
      stderr: "pipe",
      detached: true,
    })
    const output = new OutputCommands(this.environment, this.logger, request.step, request.outputs, request.state)
    let escalation: ReturnType<typeof setTimeout> | undefined
    const kill = (signal: NodeJS.Signals) => {
      try {
        process.kill(-child.pid, signal)
      } catch (error) {
        if (!(error instanceof Error) || !("code" in error) || error.code !== "ESRCH") throw error
      }
    }
    const abort = () => {
      kill("SIGTERM")
      escalation = setTimeout(() => kill("SIGKILL"), 5000)
      escalation.unref()
    }
    request.signal.addEventListener("abort", abort, { once: true })
    if (request.signal.aborted) abort()
    let code: number
    try {
      ;[code] = await Promise.all([child.exited, output.consume(child.stdout), output.consume(child.stderr)])
    } finally {
      request.signal.removeEventListener("abort", abort)
      clearTimeout(escalation)
    }
    await commands.collect(this.environment, request.outputs, request.state)
    request.signal.throwIfAborted()
    if (code !== 0) throw new Error(`Process exited with code ${code}`)
  }
}
