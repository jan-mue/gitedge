import { exportJWK, generateKeyPair, SignJWT } from "jose"
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest"
import adapter from "../api/compile.ts"

let keys: Awaited<ReturnType<typeof generateKeyPair>>
let jwk: Awaited<ReturnType<typeof exportJWK>>

beforeAll(async () => {
  keys = await generateKeyPair("RS256")
  jwk = { ...(await exportJWK(keys.publicKey)), kid: "compiler-tests", alg: "RS256" }
})

beforeEach(() => {
  vi.stubEnv("COMPILER_CALLER_PROJECT_ID", "prj_backend")
  vi.stubEnv("VERCEL_ENV", "preview")
  vi.stubEnv("VERCEL_TARGET_ENV", "")
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: URL) => {
      expect(String(url)).toBe("https://oidc.vercel.com/.well-known/jwks")
      return Response.json({ keys: [jwk] })
    }),
  )
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

async function token(claims: Record<string, string | number | undefined> = {}): Promise<string> {
  const now = Math.floor(Date.now() / 1000)
  return new SignJWT({
    iss: "https://oidc.vercel.com/test-team",
    aud: "https://vercel.com/test-team",
    sub: "owner:test-team:project:backend:environment:preview",
    owner_id: "team_tests",
    project_id: "prj_backend",
    environment: "preview",
    iat: now,
    exp: now + 300,
    ...claims,
  })
    .setProtectedHeader({ alg: "RS256", kid: "compiler-tests" })
    .sign(keys.privateKey)
}

function request(identity?: string): Request {
  return new Request("https://compiler.vercel.app/api/compile", {
    method: "POST",
    headers: identity ? { "x-vercel-trusted-oidc-idp-token": identity } : {},
    body: JSON.stringify({
      version: 1,
      filename: "ci.yaml",
      source: "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hello\n",
      event: { name: "push", ref: "refs/heads/main" },
    }),
  })
}

test("the production adapter verifies a signed backend identity through Vercel's SDK", async () => {
  const response = await adapter.fetch(request(await token()))
  expect(response.status).toBe(200)
  expect(await response.json()).toMatchObject({ version: 1, matched: true })
})

test.each([
  { project_id: "prj_other" },
  { environment: "production" },
  { iss: "https://untrusted.example" },
  { exp: 1 },
  { sub: undefined },
])("rejects invalid identity claims %j", async (claims) => {
  expect((await adapter.fetch(request(await token(claims)))).status).toBe(401)
})

test("rejects absent, malformed and forged tokens", async () => {
  const signed = await token()
  for (const identity of [undefined, "malformed", `${signed.slice(0, signed.lastIndexOf("."))}.AA`]) {
    expect((await adapter.fetch(request(identity))).status).toBe(401)
  }
})

test("fails closed when the caller project configuration is missing or broad", async () => {
  const identity = await token()
  for (const caller of ["", "*"]) {
    vi.stubEnv("COMPILER_CALLER_PROJECT_ID", caller)
    expect((await adapter.fetch(request(identity))).status).toBe(500)
  }
})
