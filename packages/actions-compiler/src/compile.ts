import type { MappingToken } from "@actions/workflow-parser/templates/tokens/index"
import type { CompiledJob } from "@gitedge/actions-runner/workflow"
import { WorkflowDocument } from "./compiler/document"
import { JobCompiler } from "./compiler/jobs"
import { WorkflowTrigger } from "./compiler/triggers"
import {
  type CompiledWorkflow,
  type CompileRequest,
  compiledWorkflowSchema,
  compileRequestSchema,
} from "./domain/compiled-workflow"

export { CompileError } from "./compiler/document"
export const MAX_IR_BYTES = 4 * 1024 * 1024
const MAX_JOBS = 256

class WorkflowCompiler {
  constructor(private readonly document: WorkflowDocument) {}

  compile(): CompiledWorkflow {
    const { document } = this
    const { root, request, template } = document
    const shared = document.fields(root, ["name", "on", "jobs", "env", "defaults", "permissions"])
    document.permissions(root.find("permissions"))
    const trigger = new WorkflowTrigger(document)
    const inputs = trigger.inputs()
    return compiledWorkflowSchema.parse({
      version: 2,
      matched: trigger.matches(),
      workflowName: shared.name || request.filename.split("/").pop(),
      dispatch: "workflow_dispatch" in template.events,
      env: shared.env,
      defaults: shared.defaults,
      inputs,
      jobs: this.jobs(inputs),
    })
  }

  private jobs(inputs: CompiledWorkflow["inputs"]): CompiledJob[] {
    const { document } = this
    const jobMap = document.root.find("jobs")?.assertMapping("jobs")
    if (!jobMap) return document.fail("Workflow must define jobs")
    const keys = new Map(
      [...jobMap].map((pair) => {
        const key = pair.key.assertString("job id").value
        return [key.toLowerCase(), key]
      }),
    )
    const jobs: CompiledJob[] = []
    let bytes = 0
    for (const [index, pair] of [...jobMap].entries()) {
      const key = pair.key.assertString("job id").value
      const token = pair.value.assertMapping("job")
      const converted = document.template.jobs[index]
      if (converted?.type !== "job") return document.fail("Reusable workflows are not supported", token)
      for (const job of new JobCompiler(document, key, token, converted, keys, inputs).compile()) {
        bytes += JSON.stringify(job).length
        if (bytes > MAX_IR_BYTES || jobs.length >= MAX_JOBS)
          document.fail("Compiled workflow exceeds the job/manifest size limit", token)
        jobs.push(job)
      }
    }
    this.validateDependencies(jobs, jobMap)
    return jobs
  }

  private validateDependencies(jobs: CompiledJob[], token: MappingToken): void {
    const visiting = new Set<string>()
    const visited = new Set<string>()
    const dependencies = new Map(jobs.map((job) => [job.key, job.needs]))
    const visit = (key: string): void => {
      if (visiting.has(key)) this.document.fail("Workflow dependency graph contains a cycle", token)
      if (visited.has(key)) return
      visiting.add(key)
      for (const dependency of dependencies.get(key) || []) visit(dependency)
      visiting.delete(key)
      visited.add(key)
    }
    for (const key of dependencies.keys()) visit(key)
  }
}

export async function compileWorkflow(input: CompileRequest): Promise<CompiledWorkflow> {
  const document = await WorkflowDocument.parse(compileRequestSchema.parse(input))
  return new WorkflowCompiler(document).compile()
}
