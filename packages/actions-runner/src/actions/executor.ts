import { realpathSync } from "node:fs"
import { resolve } from "node:path"
import type { JobStatus } from "../domain/job.ts"
import { type ActionStep, type Environment, type JsonValue, stringify, type WorkflowStep } from "../domain/workflow.ts"
import type { ExpressionEngine } from "../expressions/evaluator.ts"
import type { ExecutionScope, JobEnvironment } from "../runtime/environment.ts"
import { inside, type Workspace } from "../runtime/files.ts"
import type { JobLogger } from "../runtime/logger.ts"
import type { ProcessExecutor } from "../runtime/process.ts"
import type { ActionResolver } from "./resolver.ts"

interface PostAction {
  file: string
  environment: Environment
  scope: ExecutionScope
  condition: JsonValue
  step: string
  state: Environment
}
export interface ActionRequest {
  step: ActionStep
  scope: ExecutionScope
  environment: Environment
  status: JobStatus
  id: string
  outputs: Environment
  signal: AbortSignal
  runSteps: (
    steps: WorkflowStep[],
    scope: ExecutionScope,
    environment: Environment,
    parent: string,
  ) => Promise<JobStatus>
}

/** Resolves immutable prepared actions; each invocation owns its inputs and state. */
export class ActionExecutor {
  private readonly posts: PostAction[] = []
  private readonly node = nodeBinary()
  constructor(
    private readonly resolver: ActionResolver,
    private readonly expressions: ExpressionEngine,
    private readonly process: ProcessExecutor,
    private readonly workspace: Workspace,
    private readonly environment: JobEnvironment,
    private readonly logger: JobLogger,
  ) {}

  async run(request: ActionRequest): Promise<void> {
    const { step, scope, status, id, outputs, signal } = request
    const uses = stringify(await this.expressions.interpolate(step.uses, scope.expressionContext(), status))
    const action = await this.resolver.resolve(uses)
    const github = scope.context.github
    const child = scope.child({
      github: {
        ...(typeof github === "object" && github !== null && !Array.isArray(github) ? github : {}),
        action_path: action.directory,
        action_repository: action.repository,
        action_ref: action.reference,
      },
    })
    child.environment = request.environment
    const defaults = Object.fromEntries(
      Object.entries(action.definition.inputs).map(([name, definition]) => [name, definition.default ?? ""]),
    )
    const inputs = {
      ...(await this.expressions.environment(defaults, child.expressionContext(), status)),
      ...(await this.expressions.environment(step.with, scope.expressionContext(), status)),
    }
    child.context.inputs = inputs
    const environment: Environment = {
      ...request.environment,
      GITHUB_ACTION_PATH: action.directory,
      GITHUB_ACTION_REPOSITORY: action.repository,
      GITHUB_ACTION_REF: action.reference,
    }
    for (const [name, value] of Object.entries(inputs))
      environment[`INPUT_${name.replace(/ /g, "_").toUpperCase()}`] = value
    const runs = action.definition.runs
    if (runs.using === "composite") {
      const result = await request.runSteps(runs.steps, child, environment, id)
      for (const [name, definition] of Object.entries(action.definition.outputs))
        outputs[name] = stringify(
          await this.expressions.interpolate(definition.value, child.expressionContext(), result),
        )
      if (result !== "success") throw new Error(`Composite action ${uses}: ${result}`)
      return
    }
    const entrypoint = (path: string) => inside(action.repositoryRoot, resolve(action.directory, path))
    const state: Environment = {}
    if (runs.post)
      this.posts.push({
        file: entrypoint(runs.post),
        environment,
        scope: child,
        condition: runs["post-if"] ?? "always()",
        step: id,
        state,
      })
    if (
      runs.pre &&
      (await this.expressions.condition(runs["pre-if"] ?? "always()", child.expressionContext(), status))
    ) {
      await this.process.run({
        command: this.node,
        args: [entrypoint(runs.pre)],
        cwd: this.workspace.source,
        environment,
        step: id,
        outputs,
        state,
        signal,
      })
    }
    await this.process.run({
      command: this.node,
      args: [entrypoint(runs.main)],
      cwd: this.workspace.source,
      environment: { ...environment, ...stateEnvironment(state) },
      step: id,
      outputs,
      state,
      signal,
    })
  }

  async cleanup(status: JobStatus): Promise<JobStatus> {
    let result = status
    const signal = AbortSignal.timeout(15000)
    for (const post of this.posts.toReversed()) {
      try {
        post.scope.context.job = { status: result }
        if (!(await this.expressions.condition(post.condition, post.scope.expressionContext(), result))) continue
        this.logger.emit("Post action cleanup", post.step)
        await this.process.run({
          command: this.node,
          args: [post.file],
          environment: { ...this.environment.snapshot(post.environment), ...stateEnvironment(post.state) },
          cwd: this.workspace.source,
          step: post.step,
          outputs: {},
          state: post.state,
          signal,
        })
      } catch (error) {
        this.logger.emit(error instanceof Error ? error.message : String(error), post.step, "failure")
        if (result !== "cancelled") result = "failure"
      }
    }
    return result
  }
}
function stateEnvironment(state: Environment): Environment {
  return Object.fromEntries(Object.entries(state).map(([key, value]) => [`STATE_${key}`, value]))
}

function nodeBinary(): string {
  const configured = Bun.env.GITEDGE_NODE_BINARY
  if (configured) return configured
  const bun = realpathSync(process.execPath)
  // --bun inserts a node shim in PATH; action entrypoints require the real Node runtime.
  for (const directory of (Bun.env.PATH || "").split(":")) {
    const candidate = Bun.which("node", { PATH: directory })
    if (candidate && realpathSync(candidate) !== bun) return candidate
  }
  throw new Error("The prepared image must contain a Node runtime for JavaScript actions")
}
