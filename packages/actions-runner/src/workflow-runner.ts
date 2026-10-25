import { ActionExecutor } from "./actions/executor.ts"
import { ActionResolver } from "./actions/resolver.ts"
import type { JobResult, JobSpec, JobStatus, LogSink } from "./domain/job.ts"
import type { JsonObject } from "./domain/workflow.ts"
import { ExpressionEngine } from "./expressions/evaluator.ts"
import { ExecutionScope, JobEnvironment } from "./runtime/environment.ts"
import { Workspace } from "./runtime/files.ts"
import { JobLogger } from "./runtime/logger.ts"
import { ProcessExecutor } from "./runtime/process.ts"
import { StepExecutor } from "./runtime/steps.ts"
import { type CacheClient, ControllerCacheClient } from "./storage/cache-client.ts"
import { StorageServer } from "./storage/server.ts"

export interface RunnerOptions {
  root: string
  actions?: string
  signal: AbortSignal
  log: LogSink
  cache?: CacheClient
  restoreArtifacts?: () => Promise<void>
}
/** One instance executes one expanded job and disposes all of its resources. */
export class WorkflowRunner {
  constructor(
    private readonly input: JobSpec,
    private readonly options: RunnerOptions,
  ) {}
  async run(): Promise<JobResult> {
    const { input, options } = this
    const workflow = input.workflow,
      job = input.job.config
    const workspace = new Workspace(options.root)
    await workspace.prepare(input.event)
    const storage: StorageServer = await StorageServer.start({
      root: workspace.state,
      run: input.env.GITHUB_RUN_ID || "local",
      job: input.attempt.id,
      cache: options.cache || new ControllerCacheClient(input.cache_url, options.signal),
      restoreArtifacts: options.restoreArtifacts,
    })
    const logger = new JobLogger(options.log, Object.values(input.secrets))
    try {
      const environment = new JobEnvironment(input, workspace, storage.environment)
      const expressions = new ExpressionEngine(workspace)
      const github = environment.github()
      github.workflow = workflow.name || ""
      const context: JsonObject = {
        github,
        runner: {
          os: "Linux",
          arch: environment.protected.RUNNER_ARCH,
          temp: workspace.temporary,
          tool_cache: environment.protected.RUNNER_TOOL_CACHE,
          environment: "self-hosted",
        },
        matrix: input.job.matrix,
        needs: input.needs,
        inputs: input.inputs,
        secrets: input.secrets,
        vars: input.vars,
        job: { status: "success" },
        strategy: input.job.strategy,
      }
      const scope = new ExecutionScope(context)
      scope.environment = environment.snapshot()
      const dependencyStatus = Object.values(input.needs).some((need) => need.result !== "success")
        ? "failure"
        : "success"
      if (!(await expressions.condition(job.if, scope.expressionContext(), dependencyStatus)))
        return { status: "skipped", steps: {}, outputs: {} }
      const process = new ProcessExecutor(workspace, environment, logger)
      const resolver = new ActionResolver(workspace.source, options.actions || "/opt/gitedge/actions")
      const actions = new ActionExecutor(resolver, expressions, process, workspace, environment, logger)
      const steps = new StepExecutor(
        workflow,
        job,
        expressions,
        environment,
        process,
        actions,
        workspace,
        logger,
        options.signal,
      )
      let status: JobStatus = "failure"
      try {
        status = await steps.runAll(job.steps, scope)
      } finally {
        status = await actions.cleanup(options.signal.aborted ? "cancelled" : status)
      }
      scope.context.job = { status }
      return {
        status,
        steps: scope.steps,
        outputs: await expressions.environment(job.outputs, scope.expressionContext(), status),
      }
    } finally {
      await storage.close()
    }
  }
}
