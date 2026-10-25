import { parse } from "yaml"
import { z } from "zod"
import type { CompiledJob, WorkflowContext } from "./compiled-workflow.ts"
import { compiledStepSchema, jsonValueSchema } from "./compiled-workflow.ts"

const expression = jsonValueSchema
const stepSchema = z.union([
  compiledStepSchema.options[0]
    .omit({ kind: true })
    .extend({ id: z.string().optional() })
    .transform((step) => ({ ...step, kind: "run" as const })),
  compiledStepSchema.options[1]
    .omit({ kind: true })
    .extend({ id: z.string().optional() })
    .transform((step) => ({ ...step, kind: "action" as const })),
])
const actionBase = z.object({
  inputs: z.record(z.string(), z.object({ default: expression.optional() })).default({}),
  outputs: z.record(z.string(), z.object({ value: expression.optional() })).default({}),
})
const actionSchema = actionBase.extend({
  runs: z.discriminatedUnion("using", [
    z.object({ using: z.literal("composite"), steps: z.array(stepSchema) }),
    z.object({
      using: z.enum(["node12", "node16", "node20", "node24"]),
      main: z.string(),
      pre: z.string().optional(),
      post: z.string().optional(),
      "pre-if": expression.optional(),
      "post-if": expression.optional(),
    }),
  ]),
})
export type JsonValue = z.infer<typeof expression>
export type JsonObject = Record<string, JsonValue>
export type Environment = Record<string, string>
export type Expressions = Record<string, JsonValue>
export type Workflow = WorkflowContext
export type WorkflowJob = CompiledJob["config"]
export type WorkflowStep = z.infer<typeof stepSchema>
export type ShellStep = Extract<WorkflowStep, { kind: "run" }>
export type ActionStep = Extract<WorkflowStep, { kind: "action" }>
export type Action = z.infer<typeof actionSchema>
export function parseAction(source: string): Action {
  return actionSchema.parse(parse(source))
}
export function stringify(value: JsonValue | undefined): string {
  return value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value)
}
