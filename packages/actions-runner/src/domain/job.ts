import { z } from "zod"
import { compiledJobSchema, expressionsSchema, workflowContextSchema } from "./compiled-workflow.ts"

const statusSchema = z.enum(["success", "failure", "cancelled", "skipped"])
const strings = z.record(z.string(), z.string())
export const jobSchema = z.object({
  version: z.literal(4),
  attempt: z
    .object({ id: z.uuid(), job_id: z.string(), generation: z.number().int().positive(), fence: z.uuid() })
    .strict(),
  workflow: workflowContextSchema,
  job: compiledJobSchema,
  inputs: expressionsSchema.default({}),
  timeout_seconds: z.number().positive().default(1200),
  restore_url: z.string().url().optional(),
  report_url: z.string().url().optional(),
  report_token: z.string().optional(),
  cache_url: z.string().url().optional(),
  event_name: z.string().default(""),
  actor: z.string().default(""),
  event: z.record(z.string(), z.json()).default({}),
  env: strings.default({}),
  needs: z.record(z.string(), z.object({ result: statusSchema, outputs: strings.default({}) })).default({}),
  secrets: strings.default({}),
  vars: strings.default({}),
})
export type JobInput = z.input<typeof jobSchema>
export type JobSpec = z.output<typeof jobSchema>
export type JobStatus = z.infer<typeof statusSchema>

export interface StepResult {
  outcome: JobStatus
  conclusion: JobStatus
  outputs: Record<string, string>
}

export interface JobResult {
  status: JobStatus
  steps: Record<string, StepResult>
  outputs: Record<string, string>
  error?: string
}

export interface LogEntry {
  jobID?: string
  attemptID?: string
  generation?: number
  fence?: string
  msg: string
  stepID?: string[]
  stepResult?: JobStatus
}

export interface LogSink {
  write(entry: LogEntry): void | Promise<void>
  close(): Promise<void>
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
