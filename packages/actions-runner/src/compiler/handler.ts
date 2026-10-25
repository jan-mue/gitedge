import { timingSafeEqual } from "node:crypto"
import { compileRequestSchema } from "../domain/compiled-workflow"
import { CompileError, compileWorkflow, MAX_IR_BYTES } from "./compile"

const BODY_LIMIT = 2 * 1024 * 1024
function authorized(request: Request): boolean {
  const token = process.env.COMPILER_TOKEN
  if (!token) return false
  const actual = new TextEncoder().encode(request.headers.get("authorization") || "")
  const expected = new TextEncoder().encode(`Bearer ${token}`)
  return actual.length === expected.length && timingSafeEqual(actual, expected)
}
async function body(request: Request): Promise<string | undefined> {
  if (Number(request.headers.get("content-length")) > BODY_LIMIT) return undefined
  const reader = request.body?.getReader()
  if (!reader) return ""
  const chunks: Uint8Array[] = []
  let length = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done)
        return new TextDecoder().decode(await new Blob(chunks.map((chunk) => new Uint8Array(chunk))).arrayBuffer())
      length += value.byteLength
      if (length > BODY_LIMIT) {
        await reader.cancel()
        return undefined
      }
      chunks.push(value)
    }
  } finally {
    reader.releaseLock()
  }
}
export async function handleCompile(request: Request): Promise<Response> {
  const path = new URL(request.url).pathname
  if (path === "/healthz" && request.method === "GET") return new Response("ok")
  if (path !== "/api/compile") return new Response("Not found", { status: 404 })
  if (request.method !== "POST") return new Response("Method not allowed", { status: 405, headers: { Allow: "POST" } })
  if (!authorized(request)) return new Response("Unauthorized", { status: 401 })
  const headers = { "Cache-Control": "private, no-store" }
  try {
    const text = await body(request)
    if (text === undefined) return Response.json({ error: "request_too_large" }, { status: 413, headers })
    let input: unknown
    try {
      input = JSON.parse(text)
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error
      return Response.json(
        { error: "invalid_json", issues: [{ message: "Request body must be JSON" }] },
        { status: 422, headers },
      )
    }
    const validated = compileRequestSchema.safeParse(input)
    if (!validated.success)
      return Response.json(
        {
          error: "invalid_request",
          issues: validated.error.issues.map((issue) => ({ message: issue.message, path: issue.path })),
        },
        { status: 422, headers },
      )
    const output = JSON.stringify(await compileWorkflow(validated.data))
    if (new TextEncoder().encode(output).byteLength > MAX_IR_BYTES)
      throw new CompileError([{ filename: validated.data.filename, message: "Compiled workflow exceeds 4 MiB" }])
    return new Response(output, { headers: { ...headers, "Content-Type": "application/json" } })
  } catch (error) {
    if (error instanceof CompileError)
      return Response.json({ error: "invalid_workflow", issues: error.issues }, { status: 422, headers })
    console.error("Workflow compiler internal failure", error instanceof Error ? error.name : "InternalError")
    return Response.json({ error: "internal_error" }, { status: 500, headers })
  }
}
