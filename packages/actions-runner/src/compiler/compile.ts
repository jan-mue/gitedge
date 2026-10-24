import { isDeepStrictEqual } from "node:util"
import { data, Evaluator, Lexer, Parser } from "@actions/expressions"
import {
  convertWorkflowTemplate,
  isBasicExpression,
  isMapping,
  isSequence,
  NoOperationTraceWriter,
  parseWorkflow,
} from "@actions/workflow-parser"
import type { EventsConfig } from "@actions/workflow-parser/model/workflow-template"
import type { TemplateContext } from "@actions/workflow-parser/templates/template-context"
import type { MappingToken, TemplateToken } from "@actions/workflow-parser/templates/tokens/index"
import { z } from "zod"
import {
  type CompiledJob,
  type CompiledWorkflow,
  type CompileRequest,
  compiledJobSchema,
  compiledWorkflowSchema,
  compileRequestSchema,
  type JsonValue,
} from "../domain/compiled-workflow.ts"

export interface CompileIssue {
  filename: string
  message: string
  line?: number
  column?: number
}
export class CompileError extends Error {
  constructor(readonly issues: CompileIssue[]) {
    super(issues.map((issue) => issue.message).join("\n"))
  }
}
const MAX_JOBS = 256
export const MAX_IR_BYTES = 4 * 1024 * 1024
function fail(filename: string, message: string, token?: TemplateToken): never {
  throw new CompileError([{ filename, message, line: token?.line, column: token?.col }])
}
function check(context: TemplateContext, filename: string): void {
  if (context.errors.count)
    throw new CompileError(
      context.errors.getErrors().map((error) => ({
        filename,
        message: error.rawMessage,
        line: error.range?.start.line,
        column: error.range?.start.column,
      })),
    )
}
function value(token: TemplateToken, filename = "workflow"): JsonValue {
  if (isBasicExpression(token)) return `\${{ ${token.expression} }}`
  if (isSequence(token)) return [...token].map((item) => value(item, filename))
  if (isMapping(token))
    return Object.fromEntries(
      [...token].map((pair) => {
        if (pair.key.isExpression) fail(filename, "Expression insertion is not supported", pair.key)
        return [pair.key.assertString("mapping key").value, value(pair.value, filename)]
      }),
    )
  return token.toJSON() as JsonValue
}
function record(token: MappingToken, allowed: string[], filename: string): Record<string, JsonValue> {
  const result: Record<string, JsonValue> = {}
  for (const pair of token) {
    if (pair.key.isExpression) fail(filename, "Expression insertion is not supported", pair.key)
    const key = pair.key.assertString("property").value
    if (!allowed.includes(key)) fail(filename, `Unsupported workflow feature: ${key}`, pair.key)
    result[key] = value(pair.value, filename)
  }
  return result
}
function expressionData(input: JsonValue): data.ExpressionData {
  if (input === null) return new data.Null()
  if (Array.isArray(input)) return new data.Array(...input.map(expressionData))
  switch (typeof input) {
    case "string":
      return new data.StringData(input)
    case "number":
      return new data.NumberData(input)
    case "boolean":
      return new data.BooleanData(input)
    default:
      return new data.Dictionary(...Object.entries(input).map(([key, item]) => ({ key, value: expressionData(item) })))
  }
}
function staticValue(
  input: JsonValue | undefined,
  context: Record<string, JsonValue>,
  filename: string,
  token: TemplateToken,
): JsonValue {
  if (typeof input !== "string" || !input.startsWith("${{")) return input ?? null
  try {
    const expression = input.slice(3, -2)
    const tree = new Parser(new Lexer(expression).lex().tokens, Object.keys(context), []).parse()
    const scope = expressionData(context)
    if (scope.kind !== data.Kind.Dictionary) throw new Error("Invalid compile context")
    const result = new Evaluator(tree, scope).evaluate()
    if (result.kind === data.Kind.Null) return null
    if ("value" in result) return result.value
    fail(filename, "Expected a scalar static expression", token)
  } catch (error) {
    if (error instanceof CompileError) throw error
    fail(
      filename,
      `Job planning requires a static matrix/input expression: ${error instanceof Error ? error.message : String(error)}`,
      token,
    )
  }
}
function matchGlob(input: string, patterns: string[], filename: string): boolean {
  let matched = false
  for (const pattern of patterns) {
    if (/[[\]+{}\\]/.test(pattern)) fail(filename, `Unsupported filter pattern: ${pattern}`)
    const excluded = pattern.startsWith("!")
    const glob = (excluded ? pattern.slice(1) : pattern)
      .split(/(\*\*\/|\*\*|\*|\?)/)
      .map((part) => {
        if (part === "**/") return "(?:.*/)?"
        if (part === "**") return ".*"
        if (part === "*") return "[^/]*"
        if (part === "?") return "[^/]"
        return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      })
      .join("")
    if (new RegExp(`^${glob}$`).test(input)) matched = !excluded
  }
  return matched
}
function matches(events: EventsConfig, request: CompileRequest): boolean {
  const { event, filename } = request
  if (!(event.name in events)) return false
  const filters = z
    .object({
      types: z.array(z.string()).optional(),
      branches: z.array(z.string()).optional(),
      "branches-ignore": z.array(z.string()).optional(),
      tags: z.array(z.string()).optional(),
      "tags-ignore": z.array(z.string()).optional(),
      paths: z.array(z.string()).optional(),
      "paths-ignore": z.array(z.string()).optional(),
    })
    .parse(events[event.name] || {})
  if (filters.types && !filters.types.includes(event.action || "")) return false
  if (
    event.name === "pull_request" &&
    !filters.types &&
    event.action &&
    !["opened", "synchronize", "reopened"].includes(event.action)
  )
    return false
  const tag = event.ref.startsWith("refs/tags/")
  const included = tag ? filters.tags : filters.branches
  const ignored = tag ? filters["tags-ignore"] : filters["branches-ignore"]
  const other = tag ? filters.branches || filters["branches-ignore"] : filters.tags || filters["tags-ignore"]
  const ref = (event.name === "pull_request" ? event.baseRef || event.ref : event.ref).replace(
    /^refs\/(heads|tags)\//,
    "",
  )
  if (
    (other && !included) ||
    (included && !matchGlob(ref, included, filename)) ||
    (ignored && matchGlob(ref, ignored, filename))
  )
    return false
  const paths = event.changedPaths || []
  if (!tag && !paths.length && (filters.paths || filters["paths-ignore"])) return false
  return (
    tag ||
    ((!filters.paths || paths.some((path) => matchGlob(path, filters.paths || [], filename))) &&
      (!filters["paths-ignore"] ||
        !paths.length ||
        !paths.every((path) => matchGlob(path, filters["paths-ignore"] || [], filename))))
  )
}
function matrixVariants(token: TemplateToken | undefined, filename: string): Record<string, JsonValue>[] {
  if (!token) return [{}]
  if (!isMapping(token)) fail(filename, "Dynamic strategy.matrix is not supported", token)
  const literal = (item: TemplateToken): boolean =>
    !item.isExpression &&
    (!isMapping(item) || [...item].every((pair) => literal(pair.key) && literal(pair.value))) &&
    (!isSequence(item) || [...item].every(literal))
  if (!literal(token)) fail(filename, "Only literal static matrices are supported", token)
  const matrix = value(token) as Record<string, JsonValue>
  const { include = [], exclude = [], ...rawAxes } = matrix
  const axes = z.record(z.string(), z.array(z.json())).safeParse(rawAxes)
  const inclusions = z.array(z.record(z.string(), z.json())).safeParse(include)
  const exclusions = z.array(z.record(z.string(), z.json())).safeParse(exclude)
  if (!axes.success || !inclusions.success || !exclusions.success)
    fail(filename, "Matrix axes must be arrays and include/exclude must be arrays of mappings", token)
  let original: Record<string, JsonValue>[] = [{}]
  for (const [key, values] of Object.entries(axes.data)) {
    if (!values.length) fail(filename, "Matrix axes must contain at least one value", token)
    if (original.length * values.length > MAX_JOBS) fail(filename, "Matrix exceeds 256 jobs", token)
    original = original.flatMap((item) => values.map((value) => ({ ...item, [key]: value })))
  }
  if (!Object.keys(axes.data).length) original = []
  original = original.filter(
    (item) =>
      !exclusions.data.some((exclude) =>
        Object.entries(exclude).every(([key, value]) => isDeepStrictEqual(item[key], value)),
      ),
  )
  const expanded = original.map((item) => ({ ...item })),
    extra: Record<string, JsonValue>[] = []
  for (const inclusion of inclusions.data) {
    let merged = false
    original.forEach((source, index) => {
      if (
        Object.entries(inclusion).every(([key, value]) => !(key in source) || isDeepStrictEqual(source[key], value))
      ) {
        expanded[index] = { ...expanded[index], ...inclusion }
        merged = true
      }
    })
    if (!merged) extra.push(inclusion)
    if (expanded.length + extra.length > MAX_JOBS) fail(filename, "Matrix exceeds 256 jobs", token)
  }
  return Object.keys(axes.data).length || inclusions.data.length ? [...expanded, ...extra] : [{}]
}
function inputs(events: EventsConfig, request: CompileRequest): Record<string, JsonValue> {
  if (request.event.name !== "workflow_dispatch") return {}
  const result: Record<string, JsonValue> = {}
  const supplied = request.event.inputs || {}
  for (const [key, input] of Object.entries(events.workflow_dispatch?.inputs || {})) {
    if (input.type === "environment") fail(request.filename, "Environment dispatch inputs are not supported")
    const selected = supplied[key] ?? input.default
    if (selected === undefined && input.required) fail(request.filename, `Required dispatch input: ${key}`)
    if (input.type === "boolean") {
      if (selected !== undefined && ![true, false, "true", "false"].includes(selected as string))
        fail(request.filename, `Invalid boolean input: ${key}`)
      result[key] = selected === true || selected === "true"
    } else {
      if (typeof selected === "object") fail(request.filename, `Invalid dispatch input: ${key}`)
      const text = String(selected ?? "")
      if (input.options && !input.options.includes(text)) fail(request.filename, `Invalid choice input: ${key}`)
      result[key] = text
    }
  }
  for (const key of Object.keys(supplied))
    if (!(key in result)) fail(request.filename, `Unknown dispatch input: ${key}`)
  return result
}

export async function compileWorkflow(input: CompileRequest): Promise<CompiledWorkflow> {
  const request = compileRequestSchema.parse(input),
    { filename } = request
  if (new TextEncoder().encode(request.source).byteLength > 1024 * 1024) fail(filename, "Workflow source exceeds 1 MiB")
  const parsed = parseWorkflow({ name: filename, content: request.source }, new NoOperationTraceWriter())
  check(parsed.context, filename)
  if (!parsed.value) fail(filename, "Workflow is empty")
  const template = await convertWorkflowTemplate(parsed.context, parsed.value)
  check(parsed.context, filename)
  const root = parsed.value.assertMapping("workflow")
  const shared = record(root, ["name", "on", "jobs", "env", "defaults"], filename)
  for (const event of Object.keys(template.events))
    if (!["push", "pull_request", "workflow_dispatch"].includes(event))
      fail(filename, `Unsupported workflow event: ${event}`, root.find("on"))
  const resolvedInputs = inputs(template.events, request)
  const jobs: CompiledJob[] = []
  const jobMap = root.find("jobs")?.assertMapping("jobs")
  if (!jobMap) fail(filename, "Workflow must define jobs")
  const keys = new Map(
    [...jobMap].map((pair) => [
      pair.key.assertString("job id").value.toLowerCase(),
      pair.key.assertString("job id").value,
    ]),
  )
  let bytes = 0
  for (const [jobIndex, pair] of [...jobMap].entries()) {
    const key = pair.key.assertString("job id").value,
      token = pair.value.assertMapping("job")
    const raw = record(
      token,
      [
        "name",
        "needs",
        "if",
        "runs-on",
        "env",
        "defaults",
        "outputs",
        "steps",
        "strategy",
        "timeout-minutes",
        "continue-on-error",
      ],
      filename,
    )
    const converted = template.jobs[jobIndex]
    if (converted?.type !== "job") fail(filename, "Reusable workflows are not supported", token)
    const needs = (converted.needs || []).map(
      (need) => keys.get(need.value.toLowerCase()) || fail(filename, `Unknown dependency: ${need.value}`, need),
    )
    const strategy = token.find("strategy")?.assertMapping("strategy")
    if (strategy) record(strategy, ["matrix", "fail-fast"], filename)
    const variants = matrixVariants(strategy?.find("matrix"), filename)
    if (!variants.length) fail(filename, "Matrix expansion produced no jobs", strategy)
    if (
      variants.length > 1 &&
      (!strategy?.find("fail-fast") || value(strategy.find("fail-fast") as TemplateToken) !== false)
    )
      fail(filename, "Static matrices currently require strategy.fail-fast: false", strategy)
    const stepTokens = token.find("steps")?.assertSequence("steps")
    if (!stepTokens) fail(filename, "Job must contain steps", token)
    const steps = [...stepTokens].map((stepToken, index) => {
      const fields = record(
        stepToken.assertMapping("step"),
        [
          "id",
          "name",
          "if",
          "env",
          "continue-on-error",
          "timeout-minutes",
          "run",
          "uses",
          "with",
          "shell",
          "working-directory",
        ],
        filename,
      )
      const timeout = fields["timeout-minutes"]
      if (
        timeout !== undefined &&
        !(typeof timeout === "string" && timeout.startsWith("${{")) &&
        (!Number.isFinite(Number(timeout)) || Number(timeout) <= 0)
      )
        fail(filename, "Step timeout-minutes must be positive and finite", stepToken)
      const step = converted.steps[index]
      if (!step) fail(filename, "Invalid step", stepToken)
      if (typeof fields.uses === "string" && fields.uses.startsWith("docker://"))
        fail(filename, "Docker actions are not supported", stepToken)
      return {
        ...fields,
        id: step.id,
        if: step.if ? value(step.if) : undefined,
        kind: "run" in fields ? "run" : "action",
      }
    })
    for (const [index, matrix] of variants.entries()) {
      const strategyContext = { "job-index": index, "job-total": variants.length }
      const context = {
        matrix,
        strategy: strategyContext,
        inputs: resolvedInputs,
        github: { ref: request.event.ref, event_name: request.event.name, repository: request.event.repository || "" },
      }
      const runner = staticValue(raw["runs-on"], context, filename, token)
      const labels = (Array.isArray(runner) ? runner : [runner]).map((label) =>
        staticValue(label, context, filename, token),
      )
      if (
        labels.some(
          (label) =>
            typeof label !== "string" || !/^(ubuntu-(latest|22\.04|24\.04)|linux|self-hosted|x64|ARM64)$/.test(label),
        )
      )
        fail(filename, "Only prepared Linux runner labels are supported", token.find("runs-on"))
      const timeout = Number(staticValue(raw["timeout-minutes"] ?? 20, context, filename, token))
      if (!Number.isFinite(timeout) || timeout <= 0)
        fail(filename, "timeout-minutes must be positive and finite", token.find("timeout-minutes"))
      const ignored = staticValue(raw["continue-on-error"] ?? false, context, filename, token)
      if (typeof ignored !== "boolean") fail(filename, "continue-on-error must resolve to a boolean", token)
      const suffix = Object.keys(matrix).length ? ` (${Object.values(matrix).join(", ")})` : ""
      const name = raw.name === undefined ? key + suffix : String(staticValue(raw.name, context, filename, token))
      const config = {
        if: value(converted.if),
        env: raw.env,
        defaults: raw.defaults,
        outputs: raw.outputs,
        "timeout-minutes": raw["timeout-minutes"],
        "continue-on-error": raw["continue-on-error"],
        steps,
      }
      const job = {
        id: `${key}:${index}`,
        key,
        name,
        needs,
        matrix,
        strategy: strategyContext,
        timeoutSeconds: Math.max(1, Math.floor(timeout * 60)),
        continueOnError: ignored,
        config,
      }
      bytes += JSON.stringify(job).length
      if (bytes > MAX_IR_BYTES || jobs.length >= MAX_JOBS)
        fail(filename, "Compiled workflow exceeds the job/manifest size limit", token)
      jobs.push(compiledJobSchema.parse(job))
    }
  }
  const visiting = new Set<string>(),
    visited = new Set<string>()
  const dependencies = new Map(jobs.map((job) => [job.key, job.needs]))
  function visit(key: string): void {
    if (visiting.has(key)) fail(filename, "Workflow dependency graph contains a cycle", jobMap)
    if (visited.has(key)) return
    visiting.add(key)
    for (const dependency of dependencies.get(key) || []) visit(dependency)
    visiting.delete(key)
    visited.add(key)
  }
  for (const key of dependencies.keys()) visit(key)
  return compiledWorkflowSchema.parse({
    version: 1,
    matched: matches(template.events, request),
    workflowName: shared.name || filename.split("/").pop(),
    dispatch: "workflow_dispatch" in template.events,
    env: shared.env,
    defaults: shared.defaults,
    inputs: resolvedInputs,
    jobs,
  })
}
