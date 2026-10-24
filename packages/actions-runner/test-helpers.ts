import { compileWorkflow } from "./src/compiler/compile.ts"
import type { JobInput } from "./src/domain/job.ts"

export type WorkflowFixture = Omit<JobInput, "version" | "workflow" | "job"> & { workflow: string; job: string }
export async function manifestFixture(input: WorkflowFixture): Promise<JobInput> {
  const { workflow: source, job: key, ...runtime } = input
  const compiled = await compileWorkflow({
    version: 1,
    filename: "test.yaml",
    source,
    event: { name: "workflow_dispatch", ref: "refs/heads/main" },
  })
  const job = compiled.jobs.find((job) => job.key === key)
  if (!job) throw new Error(`Missing test job: ${key}`)
  return {
    ...runtime,
    version: 1,
    workflow: { name: compiled.workflowName, env: compiled.env, defaults: compiled.defaults },
    job,
    inputs: compiled.inputs,
  }
}
