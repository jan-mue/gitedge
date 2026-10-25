import type { JobSpec, StepResult } from "../domain/job.ts"
import type { Environment, JsonObject, JsonValue } from "../domain/workflow.ts"
import type { Workspace } from "./files.ts"

export class JobEnvironment {
  private readonly exported: Environment = {}
  readonly base: Environment = {}
  readonly protected: Environment
  constructor(
    readonly input: JobSpec,
    workspace: Workspace,
    storage: Environment,
  ) {
    for (const [key, value] of Object.entries(Bun.env))
      if (value !== undefined && !/^GITEDGE_(JOB|JOB_ENCODING|JOB_ROOT|RESTORE_URL)$/.test(key)) this.base[key] = value
    const env = input.env
    this.protected = {
      ...env,
      ...storage,
      GITHUB_WORKSPACE: workspace.source,
      GITHUB_EVENT_PATH: `${workspace.root}/event.json`,
      GITHUB_EVENT_NAME: input.event_name,
      GITHUB_ACTOR: input.actor,
      GITHUB_JOB: input.job.key,
      GITHUB_ACTIONS: "true",
      CI: "true",
      GITHUB_RUN_ATTEMPT: "1",
      RUNNER_NAME: "gitedge",
      RUNNER_ENVIRONMENT: "self-hosted",
      RUNNER_OS: "Linux",
      RUNNER_ARCH: process.arch === "arm64" ? "ARM64" : "X64",
      RUNNER_TEMP: workspace.temporary,
      RUNNER_TOOL_CACHE: Bun.env.RUNNER_TOOL_CACHE || "/opt/hostedtoolcache",
      AGENT_TOOLSDIRECTORY: Bun.env.AGENT_TOOLSDIRECTORY || "/opt/hostedtoolcache",
      GITHUB_TOKEN: input.secrets.GITHUB_TOKEN || "",
    }
  }
  snapshot(...layers: Environment[]): Environment {
    const environment = { ...this.base }
    for (const layer of layers) Object.assign(environment, layer)
    return { ...environment, ...this.exported, ...this.protected }
  }
  export(values: Environment): void {
    for (const [key, value] of Object.entries(values))
      if (!/^(GITHUB_|RUNNER_|ACTIONS_|GITEDGE_)/i.test(key) && key !== "NODE_OPTIONS") this.exported[key] = value
  }
  prependPaths(paths: string[]): void {
    if (paths.length) this.exported.PATH = `${paths.reverse().join(":")}:${this.snapshot().PATH || ""}`
  }
  github(): JsonObject {
    const env = this.protected
    return {
      ...this.input.event,
      repository: env.GITHUB_REPOSITORY || "",
      repository_owner: env.GITHUB_REPOSITORY_OWNER || "",
      server_url: env.GITHUB_SERVER_URL || "",
      api_url: env.GITHUB_API_URL || "",
      graphql_url: `${env.GITHUB_SERVER_URL}/api/graphql`,
      ref: env.GITHUB_REF || "",
      sha: env.GITHUB_SHA || "",
      ref_name: (env.GITHUB_REF || "").replace(/^refs\/(heads|tags)\//, ""),
      ref_type: env.GITHUB_REF?.startsWith("refs/tags/") ? "tag" : "branch",
      workspace: env.GITHUB_WORKSPACE,
      event_path: env.GITHUB_EVENT_PATH,
      event_name: this.input.event_name,
      event: this.input.event,
      actor: this.input.actor,
      run_id: env.GITHUB_RUN_ID || "",
      run_number: env.GITHUB_RUN_NUMBER || "",
      run_attempt: "1",
      job: this.input.job.key,
      token: this.input.secrets.GITHUB_TOKEN || "",
      workflow: "",
      action_path: "",
      action_repository: "",
      action_ref: "",
    }
  }
}
export class ExecutionScope {
  readonly steps: Record<string, StepResult> = {}
  environment: Environment = {}
  constructor(readonly context: JsonObject) {}
  expressionContext(): JsonObject {
    const steps: Record<string, JsonValue> = {}
    for (const [key, value] of Object.entries(this.steps))
      steps[key] = { outcome: value.outcome, conclusion: value.conclusion, outputs: value.outputs }
    return { ...this.context, steps, env: this.environment }
  }
  child(context: JsonObject): ExecutionScope {
    return new ExecutionScope({ ...this.context, ...context })
  }
}
