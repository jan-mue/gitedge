import { createHash } from "node:crypto"
import { globSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { data, Evaluator, Lexer, Parser } from "@actions/expressions"
import { truthy } from "@actions/expressions/result"
import type { ExpressionContext, JobStatus, JsonValue } from "./types.ts"

function convert(value: unknown): data.ExpressionData {
  if (value == null) return new data.Null()
  if (typeof value === "string") return new data.StringData(value)
  if (typeof value === "boolean") return new data.BooleanData(value)
  if (typeof value === "number") return new data.NumberData(value)
  if (Array.isArray(value)) return new data.Array(...value.map(convert))
  return new data.Dictionary(...Object.entries(value).map(([key, value]) => ({ key, value: convert(value) })))
}
function plain(value: data.ExpressionData): JsonValue {
  if (value.kind === data.Kind.Dictionary)
    return Object.fromEntries(value.pairs().map(({ key, value }) => [key, plain(value)]))
  if (value.kind === data.Kind.Array) return value.values().map(plain)
  if (value.kind === data.Kind.Null) return null
  if ("value" in value) return value.value
  throw new Error("Unsupported expression value")
}
export function evaluate(expression: string, context: ExpressionContext, status: JobStatus = "success") {
  const functions = new Map<
    string,
    { name: string; minArgs: number; maxArgs: number; call: (...args: data.ExpressionData[]) => data.ExpressionData }
  >()
  for (const name of ["success", "failure", "cancelled", "always"]) {
    functions.set(name, { name, minArgs: 0, maxArgs: 0, call: () => convert(name === "always" || status === name) })
  }
  functions.set("hashfiles", {
    name: "hashFiles",
    minArgs: 1,
    maxArgs: 255,
    call: (...patterns) => {
      const workspace = (context.github as { workspace: string }).workspace
      const paths = new Set<string>()
      for (const pattern of patterns) {
        const raw = pattern.coerceString()
        for (const path of globSync(raw.replace(/^!/, ""), { cwd: workspace })) {
          const full = resolve(workspace, path)
          if (!full.startsWith(`${resolve(workspace)}/`)) throw new Error("hashFiles path escapes workspace")
          if (raw.startsWith("!")) paths.delete(full)
          else paths.add(full)
        }
      }
      const combined = createHash("sha256")
      let count = 0
      for (const path of [...paths].sort()) {
        try {
          combined.update(createHash("sha256").update(readFileSync(path)).digest())
          count++
        } catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "EISDIR") throw error
        }
      }
      return convert(count ? combined.digest("hex") : "")
    },
  })
  const ast = new Parser(new Lexer(expression.trim()).lex().tokens, Object.keys(context), [
    ...functions.values(),
  ]).parse()
  const dictionary = convert(context)
  if (dictionary.kind !== data.Kind.Dictionary) throw new Error("Invalid expression context")
  return new Evaluator(ast, dictionary, functions).evaluate()
}
export function interpolate(value: unknown, context: ExpressionContext, status: JobStatus = "success"): unknown {
  if (typeof value !== "string") return value
  const whole = value.match(/^\s*\$\{\{([\s\S]*?)\}\}\s*$/)
  if (whole) return plain(evaluate(whole[1], context, status))
  return value.replace(/\$\{\{([\s\S]*?)\}\}/g, (_, expression) => evaluate(expression, context, status).coerceString())
}
export function condition(value: unknown, context: ExpressionContext, status: JobStatus = "success"): boolean {
  if (value == null) return status === "success"
  if (typeof value === "boolean") return value && status === "success"
  const expression = String(value).replace(/^\s*\$\{\{([\s\S]*?)\}\}\s*$/, "$1")
  if (!/\b(success|failure|cancelled|always)\s*\(/.test(expression) && status !== "success") return false
  return truthy(evaluate(expression, context, status))
}
