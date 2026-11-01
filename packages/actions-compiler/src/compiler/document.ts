import {
  convertWorkflowTemplate,
  isBasicExpression,
  isMapping,
  isSequence,
  NoOperationTraceWriter,
  parseWorkflow,
} from "@actions/workflow-parser"
import type { WorkflowTemplate } from "@actions/workflow-parser/model/workflow-template"
import type { TemplateContext } from "@actions/workflow-parser/templates/template-context"
import type { MappingToken, TemplateToken } from "@actions/workflow-parser/templates/tokens/index"
import type { JsonValue } from "@gitedge/actions-runner/workflow"
import type { CompileRequest } from "../domain/compiled-workflow"

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

export class WorkflowDocument {
  private constructor(
    readonly request: CompileRequest,
    readonly root: MappingToken,
    readonly template: WorkflowTemplate,
  ) {}

  static async parse(request: CompileRequest): Promise<WorkflowDocument> {
    const { filename, source } = request
    if (new TextEncoder().encode(source).byteLength > 1024 * 1024)
      throw new CompileError([{ filename, message: "Workflow source exceeds 1 MiB" }])
    const parsed = parseWorkflow({ name: filename, content: source }, new NoOperationTraceWriter())
    check(parsed.context, filename)
    if (!parsed.value) throw new CompileError([{ filename, message: "Workflow is empty" }])
    const template = await convertWorkflowTemplate(parsed.context, parsed.value)
    check(parsed.context, filename)
    return new WorkflowDocument(request, parsed.value.assertMapping("workflow"), template)
  }

  fail(message: string, token?: TemplateToken): never {
    throw new CompileError([{ filename: this.request.filename, message, line: token?.line, column: token?.col }])
  }

  value(token: TemplateToken): JsonValue {
    if (isBasicExpression(token)) return `\${{ ${token.expression} }}`
    if (isSequence(token)) return [...token].map((item) => this.value(item))
    if (isMapping(token))
      return Object.fromEntries(
        [...token].map((pair) => {
          if (pair.key.isExpression) this.fail("Expression insertion is not supported", pair.key)
          return [pair.key.assertString("mapping key").value, this.value(pair.value)]
        }),
      )
    return token.toJSON() as JsonValue
  }

  fields(token: MappingToken, allowed: string[]): Record<string, JsonValue> {
    const result: Record<string, JsonValue> = {}
    for (const pair of token) {
      if (pair.key.isExpression) this.fail("Expression insertion is not supported", pair.key)
      const key = pair.key.assertString("property").value
      if (!allowed.includes(key)) this.fail(`Unsupported workflow feature: ${key}`, pair.key)
      result[key] = this.value(pair.value)
    }
    return result
  }

  permissions(token: TemplateToken | undefined): void {
    if (!token) return
    const permissions = this.value(token)
    if (permissions === null || typeof permissions !== "object" || Array.isArray(permissions))
      this.fail("Only contents: read permissions are supported", token)
    if (
      Object.keys(permissions).length !== 1 ||
      Object.entries(permissions).some(([key, access]) => key !== "contents" || access !== "read")
    )
      this.fail("Only contents: read permissions are supported", token)
  }
}
