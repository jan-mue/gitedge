import type { JsonValue } from "@gitedge/actions-runner/workflow"
import { minimatch } from "minimatch"
import { z } from "zod"
import type { WorkflowDocument } from "./document"

function matchGlob(input: string, patterns: string[]): boolean {
  let matched = false
  for (const pattern of patterns) {
    const excluded = pattern.startsWith("!")
    if (minimatch(input, excluded ? pattern.slice(1) : pattern, { dot: true, nonegate: true, nocomment: true }))
      matched = !excluded
  }
  return matched
}

export class WorkflowTrigger {
  constructor(private readonly document: WorkflowDocument) {
    for (const event of Object.keys(document.template.events))
      if (!["push", "pull_request", "workflow_dispatch"].includes(event))
        document.fail(`Unsupported workflow event: ${event}`, document.root.find("on"))
  }

  matches(): boolean {
    const { event } = this.document.request
    const events = this.document.template.events
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
    if ((other && !included) || (included && !matchGlob(ref, included)) || (ignored && matchGlob(ref, ignored)))
      return false
    const paths = event.changedPaths || []
    if (!tag && !paths.length && (filters.paths || filters["paths-ignore"])) return false
    return (
      tag ||
      ((!filters.paths || paths.some((path) => matchGlob(path, filters.paths || []))) &&
        (!filters["paths-ignore"] ||
          !paths.length ||
          !paths.every((path) => matchGlob(path, filters["paths-ignore"] || []))))
    )
  }

  inputs(): Record<string, JsonValue> {
    const request = this.document.request
    const events = this.document.template.events
    if (request.event.name !== "workflow_dispatch") return {}
    const result: Record<string, JsonValue> = {}
    const supplied = request.event.inputs || {}
    for (const [key, input] of Object.entries(events.workflow_dispatch?.inputs || {})) {
      if (input.type === "environment") this.document.fail("Environment dispatch inputs are not supported")
      const selected = supplied[key] ?? input.default
      if (selected === undefined && input.required) this.document.fail(`Required dispatch input: ${key}`)
      if (input.type === "boolean") {
        if (selected !== undefined && ![true, false, "true", "false"].includes(selected as string))
          this.document.fail(`Invalid boolean input: ${key}`)
        result[key] = selected === true || selected === "true"
      } else {
        if (typeof selected === "object") this.document.fail(`Invalid dispatch input: ${key}`)
        const text = String(selected ?? "")
        if (input.options && !input.options.includes(text)) this.document.fail(`Invalid choice input: ${key}`)
        result[key] = text
      }
    }
    for (const key of Object.keys(supplied)) if (!(key in result)) this.document.fail(`Unknown dispatch input: ${key}`)
    return result
  }
}
