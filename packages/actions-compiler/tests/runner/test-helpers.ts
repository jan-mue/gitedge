import type { JobInput } from "../../../actions-runner/src/domain/job.ts"
import { compileWorkflow } from "../../src/compile.ts"

export type WorkflowFixture = Omit<JobInput, "version" | "attempt" | "workflow" | "job"> & {
  workflow: string
  job: string
}
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
    version: 2,
    attempt: {
      id: "11111111-1111-4111-8111-111111111111",
      job_id: input.job,
      generation: 1,
      fence: "22222222-2222-4222-8222-222222222222",
    },
    workflow: { name: compiled.workflowName, env: compiled.env, defaults: compiled.defaults },
    job,
    inputs: compiled.inputs,
  }
}
