import { join } from "node:path"
import type { ActionExecutor } from "../actions/executor.ts"
import { errorMessage, type JobStatus, type StepResult } from "../domain/job.ts"
import {
  type Environment,
  type ShellStep,
  stringify,
  type Workflow,
  type WorkflowJob,
  type WorkflowStep,
} from "../domain/workflow.ts"
import type { ExpressionEngine } from "../expressions/evaluator.ts"
import type { ExecutionScope, JobEnvironment } from "./environment.ts"
import { inside, type Workspace, writeFile } from "./files.ts"
import type { JobLogger } from "./logger.ts"
import type { ProcessExecutor } from "./process.ts"

export class StepExecutor {
  constructor(
    private readonly workflow: Workflow,
    private readonly job: WorkflowJob,
    private readonly expressions: ExpressionEngine,
    private readonly environment: JobEnvironment,
    private readonly process: ProcessExecutor,
    private readonly actions: ActionExecutor,
    private readonly workspace: Workspace,
    private readonly logger: JobLogger,
    private readonly signal: AbortSignal,
  ) {}

  async runAll(
    steps: WorkflowStep[],
    scope: ExecutionScope,
    base: Environment = {},
    parent?: string,
  ): Promise<JobStatus> {
    let status: JobStatus = "success"
    for (const [index, step] of steps.entries()) {
      scope.context.job = { status }
      const result = await this.run(step, scope, status, base, String(index), parent)
      if (result.conclusion === "failure" || result.conclusion === "cancelled") status = result.conclusion
    }
    return this.signal.aborted ? "cancelled" : status
  }

  private async run(
    step: WorkflowStep,
    scope: ExecutionScope,
    status: JobStatus,
    base: Environment,
    generatedId: string,
    parent?: string,
  ): Promise<StepResult> {
    const id = step.id || generatedId,
      displayId = parent || id
    const result: StepResult = { outcome: "skipped", conclusion: "skipped", outputs: {} }
    const label = step.name || (step.kind === "action" ? step.uses : id)
    try {
      scope.environment = this.environment.snapshot(base)
      const workflow = await this.expressions.environment(this.workflow.env, scope.expressionContext(), status)
      scope.environment = this.environment.snapshot(base, workflow)
      const job = await this.expressions.environment(this.job.env, scope.expressionContext(), status)
      scope.environment = this.environment.snapshot(base, workflow, job)
      if (this.signal.aborted || !(await this.expressions.condition(step.if, scope.expressionContext(), status))) {
        this.logger.emit(`Skipped ${label}`, displayId, "skipped")
        return result
      }
      const values = await this.expressions.environment(step.env, scope.expressionContext(), status)
      scope.environment = {
        ...this.environment.snapshot(base, workflow, job),
        ...values,
        ...this.environment.protected,
      }
      this.logger.emit(`Run ${label}`, displayId)
      const minutes = Number(
        await this.expressions.interpolate(step["timeout-minutes"], scope.expressionContext(), status),
      )
      if (step["timeout-minutes"] !== undefined && (!Number.isFinite(minutes) || minutes <= 0))
        throw new Error("Step timeout-minutes must resolve to a positive finite number")
      const signal = minutes > 0 ? AbortSignal.any([this.signal, AbortSignal.timeout(minutes * 60000)]) : this.signal
      switch (step.kind) {
        case "run":
          await this.shell(step, scope, status, displayId, result.outputs, signal)
          break
        case "action":
          await this.actions.run({
            step,
            scope,
            status,
            environment: scope.environment,
            id: displayId,
            outputs: result.outputs,
            signal,
            runSteps: (steps, child, environment, parent) => this.runAll(steps, child, environment, parent),
          })
          break
      }
      result.outcome = "success"
      result.conclusion = "success"
    } catch (error) {
      result.outcome = this.signal.aborted ? "cancelled" : "failure"
      result.conclusion = result.outcome
      this.logger.emit(errorMessage(error), displayId)
      if (
        !this.signal.aborted &&
        (await this.expressions.interpolate(step["continue-on-error"] ?? false, scope.expressionContext(), status)) ===
          true
      )
        result.conclusion = "success"
    } finally {
      scope.steps[id] = result
    }
    this.logger.emit(`${label}: ${result.conclusion}`, displayId, result.conclusion)
    return result
  }

  private async shell(
    step: ShellStep,
    scope: ExecutionScope,
    status: JobStatus,
    id: string,
    outputs: Environment,
    signal: AbortSignal,
  ): Promise<void> {
    const defaults = { ...this.workflow.defaults?.run, ...this.job.defaults?.run }
    const shell = stringify(
      await this.expressions.interpolate(step.shell || defaults.shell || "bash", scope.expressionContext(), status),
    )
    const extension = shell === "bash" || shell === "sh" ? "sh" : shell === "python" ? "py" : "mjs"
    const script = join(this.workspace.temporary, `${crypto.randomUUID()}.${extension}`)
    await writeFile(script, stringify(await this.expressions.interpolate(step.run, scope.expressionContext(), status)))
    const command = shellCommand(shell, script)
    const cwd = inside(
      this.workspace.source,
      stringify(
        await this.expressions.interpolate(
          step["working-directory"] || defaults["working-directory"] || ".",
          scope.expressionContext(),
          status,
        ),
      ),
    )
    await this.process.run({ ...command, environment: scope.environment, cwd, step: id, outputs, state: {}, signal })
  }
}

function shellCommand(shell: string, script: string): { command: string; args: string[] } {
  switch (shell) {
    case "bash":
      return { command: "bash", args: ["--noprofile", "--norc", "-e", "-o", "pipefail", script] }
    case "sh":
      return { command: "sh", args: ["-e", script] }
    case "python":
      return { command: "python", args: [script] }
    default: {
      if (!shell.includes("{0}")) throw new Error(`Unsupported shell: ${shell}`)
      const [command, ...args] = shell.split(/\s+/)
      return { command, args: args.map((arg) => arg.replace("{0}", script)) }
    }
  }
}
