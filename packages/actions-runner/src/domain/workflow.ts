import { parse } from "yaml"
import { z } from "zod"

const expression = z.json()
const expressions = z.record(z.string(), expression)
const defaults = z.object({
  run: z.object({ shell: z.string().optional(), "working-directory": z.string().optional() }).optional(),
})
const step = z.object({
  id: z.string().optional(),
  name: z.string().optional(),
  if: expression.optional(),
  env: expressions.optional(),
  "continue-on-error": expression.optional(),
  "timeout-minutes": expression.optional(),
})
const stepSchema = z.union([
  step
    .extend({ run: z.string(), shell: z.string().optional(), "working-directory": z.string().optional() })
    .transform((value) => ({ ...value, kind: "run" as const })),
  step
    .extend({ uses: z.string(), with: expressions.optional() })
    .transform((value) => ({ ...value, kind: "action" as const })),
])
const workflowSchema = z.object({
  name: z.string().optional(),
  env: expressions.optional(),
  defaults: defaults.optional(),
  jobs: z.record(
    z.string(),
    z.object({
      if: expression.optional(),
      env: expressions.optional(),
      defaults: defaults.optional(),
      outputs: expressions.optional(),
      steps: z.array(stepSchema),
    }),
  ),
})
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
export type Workflow = z.infer<typeof workflowSchema>
export type WorkflowStep = z.infer<typeof stepSchema>
export type ShellStep = Extract<WorkflowStep, { kind: "run" }>
export type ActionStep = Extract<WorkflowStep, { kind: "action" }>
export type Action = z.infer<typeof actionSchema>
export function parseWorkflow(source: string): Workflow {
  return workflowSchema.parse(parse(source))
}
export function parseAction(source: string): Action {
  return actionSchema.parse(parse(source))
}
export function stringify(value: JsonValue | undefined): string {
  return value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value)
}
