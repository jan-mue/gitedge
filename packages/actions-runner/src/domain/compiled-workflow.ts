import { z } from "zod"

export const jsonValueSchema = z.json()
export const expressionsSchema = z.record(z.string(), jsonValueSchema)
const defaultsSchema = z
  .object({
    run: z.object({ shell: z.string().optional(), "working-directory": z.string().optional() }).strict().optional(),
  })
  .strict()
const stepBase = z.object({
  id: z.string(),
  name: z.string().optional(),
  if: jsonValueSchema.optional(),
  env: expressionsSchema.optional(),
  "continue-on-error": jsonValueSchema.optional(),
  "timeout-minutes": jsonValueSchema.optional(),
})
export const compiledStepSchema = z.discriminatedUnion("kind", [
  stepBase
    .extend({
      kind: z.literal("run"),
      run: z.string(),
      shell: z.string().optional(),
      "working-directory": z.string().optional(),
    })
    .strict(),
  stepBase.extend({ kind: z.literal("action"), uses: z.string(), with: expressionsSchema.optional() }).strict(),
])
const jobConfigurationSchema = z
  .object({
    if: jsonValueSchema.optional(),
    env: expressionsSchema.optional(),
    defaults: defaultsSchema.optional(),
    outputs: expressionsSchema.optional(),
    "timeout-minutes": jsonValueSchema.optional(),
    "continue-on-error": jsonValueSchema.optional(),
    steps: z.array(compiledStepSchema).min(1),
  })
  .strict()
export const compiledJobSchema = z
  .object({
    id: z.string().min(1),
    key: z.string().min(1),
    name: z.string(),
    needs: z.array(z.string()),
    matrix: expressionsSchema,
    strategy: expressionsSchema,
    timeoutSeconds: z.number().int().positive(),
    continueOnError: z.boolean(),
    config: jobConfigurationSchema,
  })
  .strict()
export const workflowContextSchema = z
  .object({ name: z.string(), env: expressionsSchema.optional(), defaults: defaultsSchema.optional() })
  .strict()
export type CompiledJob = z.infer<typeof compiledJobSchema>
export type WorkflowContext = z.infer<typeof workflowContextSchema>
export type JsonValue = z.infer<typeof jsonValueSchema>
