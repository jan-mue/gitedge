export type JsonValue = null | string | number | boolean | JsonValue[] | { [key: string]: JsonValue }
export type JobStatus = "success" | "failure" | "cancelled" | "skipped"
export type ExpressionMap = Record<string, unknown>
export type ExpressionContext = Record<string, unknown>

export interface WorkflowStep {
  id?: string
  name?: string
  uses?: string
  run?: string
  shell?: string
  if?: unknown
  with?: ExpressionMap
  env?: ExpressionMap
  "continue-on-error"?: unknown
  "working-directory"?: string
  "timeout-minutes"?: unknown
}

interface RunDefaults {
  run?: { shell?: string; "working-directory"?: string }
}

interface WorkflowJob {
  steps: WorkflowStep[]
  env?: ExpressionMap
  outputs?: ExpressionMap
  if?: unknown
  defaults?: RunDefaults
}

export interface Workflow {
  name?: string
  jobs: Record<string, WorkflowJob>
  env?: ExpressionMap
  defaults?: RunDefaults
}

export interface ActionMetadata {
  inputs?: Record<string, { default?: unknown }>
  outputs?: Record<string, { value: unknown }>
  runs: {
    using?: string
    main?: string
    pre?: string
    post?: string
    "pre-if"?: unknown
    "post-if"?: unknown
    steps?: WorkflowStep[]
  }
}

export interface StepResult {
  outcome: JobStatus
  conclusion: JobStatus
  outputs: Record<string, string>
}

export interface JobInput {
  workflow: string
  job: string
  timeout_seconds?: number
  dispatched_at_ms?: number
  restore_url?: string
  complete_url?: string
  event_name?: string
  actor?: string
  event?: Record<string, JsonValue>
  env: Record<string, string>
  matrix?: Record<string, JsonValue>
  needs?: Record<string, { result: JobStatus; outputs?: Record<string, string> }>
  secrets?: Record<string, string>
  vars?: Record<string, string>
}

export interface JobResult {
  status: JobStatus
  outputs: Record<string, string>
  steps: Record<string, StepResult>
  error?: string
  startup_ms?: number | null
}

export interface LogEntry {
  msg: string
  stepID?: string[]
  stepResult?: JobStatus
}

export interface RunnerContext extends ExpressionContext {
  github: Record<string, unknown>
  steps: Record<string, StepResult>
  env: NodeJS.ProcessEnv
  job: { status: JobStatus }
}
