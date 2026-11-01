import { isDeepStrictEqual } from "node:util"
import { data, Evaluator, Lexer, Parser } from "@actions/expressions"
import { isMapping, isSequence } from "@actions/workflow-parser"
import type { Job } from "@actions/workflow-parser/model/workflow-template"
import type { MappingToken, TemplateToken } from "@actions/workflow-parser/templates/tokens/index"
import {
  type CompiledJob,
  compiledJobSchema,
  compiledStepSchema,
  type JsonValue,
} from "@gitedge/actions-runner/workflow"
import { z } from "zod"
import { CompileError, type WorkflowDocument } from "./document"

const MAX_JOBS = 256

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
  document: WorkflowDocument,
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
    document.fail("Expected a scalar static expression", token)
  } catch (error) {
    if (error instanceof CompileError) throw error
    document.fail(
      `Job planning requires a static matrix/input expression: ${error instanceof Error ? error.message : String(error)}`,
      token,
    )
  }
}

function matrixVariants(token: TemplateToken | undefined, document: WorkflowDocument): Record<string, JsonValue>[] {
  if (!token) return [{}]
  if (!isMapping(token)) document.fail("Dynamic strategy.matrix is not supported", token)
  const literal = (item: TemplateToken): boolean =>
    !item.isExpression &&
    (!isMapping(item) || [...item].every((pair) => literal(pair.key) && literal(pair.value))) &&
    (!isSequence(item) || [...item].every(literal))
  if (!literal(token)) document.fail("Only literal static matrices are supported", token)
  const matrix = document.value(token) as Record<string, JsonValue>
  const { include = [], exclude = [], ...rawAxes } = matrix
  const axes = z.record(z.string(), z.array(z.json())).safeParse(rawAxes)
  const inclusions = z.array(z.record(z.string(), z.json())).safeParse(include)
  const exclusions = z.array(z.record(z.string(), z.json())).safeParse(exclude)
  if (!axes.success || !inclusions.success || !exclusions.success)
    document.fail("Matrix axes must be arrays and include/exclude must be arrays of mappings", token)
  let original: Record<string, JsonValue>[] = [{}]
  for (const [key, values] of Object.entries(axes.data)) {
    if (!values.length) document.fail("Matrix axes must contain at least one value", token)
    if (original.length * values.length > MAX_JOBS) document.fail("Matrix exceeds 256 jobs", token)
    original = original.flatMap((item) => values.map((value) => ({ ...item, [key]: value })))
  }
  if (!Object.keys(axes.data).length) original = []
  original = original.filter(
    (item) =>
      !exclusions.data.some((exclude) =>
        Object.entries(exclude).every(([key, value]) => isDeepStrictEqual(item[key], value)),
      ),
  )
  const expanded = original.map((item) => ({ ...item }))
  const extra: Record<string, JsonValue>[] = []
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
    if (expanded.length + extra.length > MAX_JOBS) document.fail("Matrix exceeds 256 jobs", token)
  }
  return Object.keys(axes.data).length || inclusions.data.length ? [...expanded, ...extra] : [{}]
}

function compileSteps(token: MappingToken, converted: Job, document: WorkflowDocument): CompiledJob["config"]["steps"] {
  const stepTokens = token.find("steps")?.assertSequence("steps")
  if (!stepTokens) document.fail("Job must contain steps", token)
  return [...stepTokens].map((stepToken, index) => {
    const fields = document.fields(stepToken.assertMapping("step"), [
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
    ])
    if (
      fields.with !== undefined &&
      (fields.with === null || typeof fields.with !== "object" || Array.isArray(fields.with))
    )
      document.fail("Dynamic action input mappings are not supported; use expressions for individual inputs", stepToken)
    const timeout = fields["timeout-minutes"]
    if (
      timeout !== undefined &&
      !(typeof timeout === "string" && timeout.startsWith("${{")) &&
      (!Number.isFinite(Number(timeout)) || Number(timeout) <= 0)
    )
      document.fail("Step timeout-minutes must be positive and finite", stepToken)
    const step = converted.steps[index]
    if (!step) document.fail("Invalid step", stepToken)
    if (typeof fields.uses === "string" && fields.uses.startsWith("docker://"))
      document.fail("Docker actions are not supported", stepToken)
    return compiledStepSchema.parse({
      ...fields,
      id: step.id,
      if: step.if ? document.value(step.if) : undefined,
      kind: "run" in fields ? "run" : "action",
    })
  })
}

function validateRunner(
  input: JsonValue | undefined,
  context: Record<string, JsonValue>,
  document: WorkflowDocument,
  token: MappingToken,
): void {
  const runner = staticValue(input, context, document, token)
  const labels = (Array.isArray(runner) ? runner : [runner]).map((label) =>
    staticValue(label, context, document, token),
  )
  if (
    labels.some(
      (label) => typeof label !== "string" || !/^(ubuntu-(latest|22\.04|24\.04)|linux|self-hosted|x64)$/.test(label),
    )
  )
    document.fail("Only prepared x64 Linux runner labels are supported", token.find("runs-on"))
}

function jobTimeout(
  input: JsonValue | undefined,
  context: Record<string, JsonValue>,
  document: WorkflowDocument,
  token: MappingToken,
): number {
  const timeout = Number(staticValue(input ?? 20, context, document, token))
  if (!Number.isFinite(timeout) || timeout <= 0)
    document.fail("timeout-minutes must be positive and finite", token.find("timeout-minutes"))
  return timeout
}

export class JobCompiler {
  private readonly fields: Record<string, JsonValue>
  private readonly needs: string[]
  private readonly steps: CompiledJob["config"]["steps"]
  private readonly variants: Record<string, JsonValue>[]

  constructor(
    private readonly document: WorkflowDocument,
    private readonly key: string,
    private readonly token: MappingToken,
    private readonly converted: Job,
    keys: ReadonlyMap<string, string>,
    private readonly inputs: Record<string, JsonValue>,
  ) {
    this.fields = document.fields(token, [
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
      "permissions",
    ])
    document.permissions(token.find("permissions"))
    this.needs = (converted.needs || []).map(
      (need) => keys.get(need.value.toLowerCase()) || document.fail(`Unknown dependency: ${need.value}`, need),
    )
    this.variants = this.matrix()
    this.steps = compileSteps(token, converted, document)
  }

  *compile(): Generator<CompiledJob> {
    for (const [index, matrix] of this.variants.entries()) yield this.variant(matrix, index)
  }

  private matrix(): Record<string, JsonValue>[] {
    const { document, token } = this
    const strategy = token.find("strategy")?.assertMapping("strategy")
    if (strategy) document.fields(strategy, ["matrix", "fail-fast"])
    const variants = matrixVariants(strategy?.find("matrix"), document)
    if (!variants.length) document.fail("Matrix expansion produced no jobs", strategy)
    if (
      variants.length > 1 &&
      (!strategy?.find("fail-fast") || document.value(strategy.find("fail-fast") as TemplateToken) !== false)
    )
      document.fail("Static matrices currently require strategy.fail-fast: false", strategy)
    return variants
  }

  private variant(matrix: Record<string, JsonValue>, index: number): CompiledJob {
    const { document, token, key, fields } = this
    const strategy = { "job-index": index, "job-total": this.variants.length }
    const { event } = document.request
    const context = {
      matrix,
      strategy,
      inputs: this.inputs,
      github: { ref: event.ref, event_name: event.name, repository: event.repository || "" },
    }
    validateRunner(fields["runs-on"], context, document, token)
    const timeout = jobTimeout(fields["timeout-minutes"], context, document, token)
    const ignored = staticValue(fields["continue-on-error"] ?? false, context, document, token)
    if (typeof ignored !== "boolean") document.fail("continue-on-error must resolve to a boolean", token)
    const suffix = Object.keys(matrix).length ? ` (${Object.values(matrix).join(", ")})` : ""
    const name = fields.name === undefined ? key + suffix : String(staticValue(fields.name, context, document, token))
    return compiledJobSchema.parse({
      id: `${key}:${index}`,
      key,
      name,
      needs: this.needs,
      matrix,
      strategy,
      timeoutSeconds: Math.max(1, Math.floor(timeout * 60)),
      continueOnError: ignored,
      config: {
        if: document.value(this.converted.if),
        env: fields.env,
        defaults: fields.defaults,
        outputs: fields.outputs,
        "timeout-minutes": fields["timeout-minutes"],
        "continue-on-error": fields["continue-on-error"],
        steps: this.steps,
      },
    })
  }
}
