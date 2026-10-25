import { data, Evaluator, Lexer, Parser } from "@actions/expressions"
import type { FunctionDefinition } from "@actions/expressions/funcs/info"
import { truthy } from "@actions/expressions/result"
import type { JobStatus } from "../domain/job.ts"
import type { Expressions, JsonObject, JsonValue } from "../domain/workflow.ts"
import { stringify } from "../domain/workflow.ts"
import type { Workspace } from "../runtime/files.ts"

function expressionData(value: JsonValue): data.ExpressionData {
  if (value === null) return new data.Null()
  switch (typeof value) {
    case "string":
      return new data.StringData(value)
    case "number":
      return new data.NumberData(value)
    case "boolean":
      return new data.BooleanData(value)
    default:
      return Array.isArray(value)
        ? new data.Array(...value.map(expressionData))
        : new data.Dictionary(...Object.entries(value).map(([key, value]) => ({ key, value: expressionData(value) })))
  }
}

function jsonValue(value: data.ExpressionData): JsonValue {
  if (value.kind === data.Kind.Dictionary)
    return Object.fromEntries(value.pairs().map(({ key, value }) => [key, jsonValue(value)]))
  if (value.kind === data.Kind.Array) return value.values().map(jsonValue)
  if (value.kind === data.Kind.Null) return null
  if ("value" in value) return value.value
  throw new Error("Unsupported expression result")
}

class HashFilesRequest extends Error {
  constructor(readonly patterns: string[]) {
    super("hashFiles requires asynchronous file access")
  }
}

export class ExpressionEngine {
  constructor(private readonly workspace: Workspace) {}

  async evaluate(expression: string, context: JsonObject, status: JobStatus): Promise<data.ExpressionData> {
    const hashes = new Map<string, string>()
    const functions = new Map<string, FunctionDefinition>()
    for (const name of ["success", "failure", "cancelled", "always"])
      functions.set(name, {
        name,
        minArgs: 0,
        maxArgs: 0,
        call: () => new data.BooleanData(name === "always" || status === name),
      })
    functions.set("hashfiles", {
      name: "hashFiles",
      minArgs: 1,
      maxArgs: 255,
      call: (...args) => {
        const patterns = args.map((arg) => arg.coerceString())
        const hash = hashes.get(JSON.stringify(patterns))
        if (hash === undefined) throw new HashFilesRequest(patterns)
        return new data.StringData(hash)
      },
    })
    const tree = new Parser(new Lexer(expression.trim()).lex().tokens, Object.keys(context), [
      ...functions.values(),
    ]).parse()
    const dictionary = expressionData(context)
    if (dictionary.kind !== data.Kind.Dictionary) throw new Error("Expression context must be an object")
    // Retrying a pure expression after an async hash preserves lazy boolean evaluation.
    for (let attempt = 0; attempt < 32; attempt++) {
      try {
        return new Evaluator(tree, dictionary, functions).evaluate()
      } catch (error) {
        if (!(error instanceof HashFilesRequest)) throw error
        hashes.set(JSON.stringify(error.patterns), await this.workspace.hashFiles(error.patterns))
      }
    }
    throw new Error("Too many hashFiles calls in one expression")
  }

  async interpolate(value: JsonValue | undefined, context: JsonObject, status: JobStatus): Promise<JsonValue> {
    if (typeof value !== "string") return value ?? null
    const whole = value.match(/^\s*\$\{\{([\s\S]*?)\}\}\s*$/)
    if (whole) return jsonValue(await this.evaluate(whole[1], context, status))
    let output = ""
    let offset = 0
    for (const match of value.matchAll(/\$\{\{([\s\S]*?)\}\}/g)) {
      output += value.slice(offset, match.index)
      output += (await this.evaluate(match[1], context, status)).coerceString()
      offset = match.index + match[0].length
    }
    return output + value.slice(offset)
  }

  async condition(value: JsonValue | undefined, context: JsonObject, status: JobStatus): Promise<boolean> {
    if (value == null) return status === "success"
    if (typeof value === "boolean") return value && status === "success"
    const expression = stringify(value).replace(/^\s*\$\{\{([\s\S]*?)\}\}\s*$/, "$1")
    if (!/\b(success|failure|cancelled|always)\s*\(/.test(expression) && status !== "success") return false
    return truthy(await this.evaluate(expression, context, status))
  }

  async environment(
    values: Expressions | undefined,
    context: JsonObject,
    status: JobStatus,
  ): Promise<Record<string, string>> {
    const result: Record<string, string> = {}
    for (const [key, value] of Object.entries(values ?? {}))
      result[key] = stringify(await this.interpolate(value, context, status))
    return result
  }
}
