import { compiledJobSchema, expressionsSchema, workflowContextSchema } from "@gitedge/actions-runner/workflow"
import { z } from "zod"

export const compiledWorkflowSchema = z
  .object({
    version: z.literal(2),
    matched: z.boolean(),
    workflowName: z.string(),
    dispatch: z.boolean(),
    env: workflowContextSchema.shape.env,
    defaults: workflowContextSchema.shape.defaults,
    inputs: expressionsSchema,
    jobs: z.array(compiledJobSchema).max(256),
  })
  .strict()
export const compileRequestSchema = z
  .object({
    version: z.literal(1),
    filename: z.string().regex(/^(?:\.gitedge\/workflow\/)?[\w.-]+\.ya?ml$/),
    source: z.string().max(1024 * 1024),
    event: z
      .object({
        name: z.enum(["push", "pull_request", "workflow_dispatch"]),
        ref: z.string().max(1024),
        action: z.string().optional(),
        baseRef: z.string().optional(),
        changedPaths: z.array(z.string()).max(10000).optional(),
        repository: z.string().optional(),
        inputs: expressionsSchema.optional(),
      })
      .strict(),
  })
  .strict()
export type CompileRequest = z.infer<typeof compileRequestSchema>
export type CompiledWorkflow = z.infer<typeof compiledWorkflowSchema>
