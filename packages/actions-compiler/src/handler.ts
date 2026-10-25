import { verifyVercelOidcToken } from "@vercel/oidc"
import { CompileError, compileWorkflow, MAX_IR_BYTES } from "./compile"
import { compileRequestSchema } from "./domain/compiled-workflow"

const BODY_LIMIT = 2 * 1024 * 1024

async function authorized(request: Request): Promise<boolean> {
  const token = request.headers.get("x-vercel-trusted-oidc-idp-token")
  if (!token) return false
  const projectId = process.env.COMPILER_CALLER_PROJECT_ID
  const environment = process.env.VERCEL_TARGET_ENV || process.env.VERCEL_ENV
  if (!projectId || projectId === "*" || !environment || environment === "*")
    throw new Error("Compiler caller project and deployment environment must be configured")

  try {
    await verifyVercelOidcToken(token, { projectId, environment, requiredClaims: ["exp", "iat", "sub"] })
    return true
  } catch (error) {
    if (
      error instanceof Error &&
      "code" in error &&
      [
        "ERR_JWT_EXPIRED",
        "ERR_JWT_CLAIM_VALIDATION_FAILED",
        "ERR_JWT_INVALID",
        "ERR_JWS_INVALID",
        "ERR_JWS_SIGNATURE_VERIFICATION_FAILED",
        "ERR_JOSE_ALG_NOT_ALLOWED",
        "ERR_JWKS_NO_MATCHING_KEY",
        "ERR_VERCEL_OIDC_TOKEN_VALIDATION",
      ].includes(String(error.code))
    )
      return false
    throw error
  }
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

export async function handleCompile(
  request: Request,
  authenticate: (request: Request) => Promise<boolean> = authorized,
): Promise<Response> {
  const path = new URL(request.url).pathname
  if (path === "/healthz" && request.method === "GET") return new Response("ok")
  if (path !== "/api/compile") return new Response("Not found", { status: 404 })
  if (request.method !== "POST") return new Response("Method not allowed", { status: 405, headers: { Allow: "POST" } })
  const headers = { "Cache-Control": "private, no-store" }
  try {
    if (!(await authenticate(request))) return new Response("Unauthorized", { status: 401, headers })
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
