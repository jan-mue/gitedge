import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

const gitPaths = [
  "/gitedge/gitedge.git/info/refs?service=git-receive-pack",
  "/gitedge/gitedge.git/info/refs?service=git-upload-pack",
  "/gitedge/gitedge.git/git-receive-pack",
  "/gitedge/gitedge.git/git-upload-pack",
  "/gitedge/gitedge.git/HEAD",
  "/gitedge/gitedge.git/objects/info/packs",
  "/gitedge/gitedge.git/objects/ab/cdef",
  "/gitedge/gitedge.git/objects/pack/pack-abc.pack",
]

async function rewrite(path: string): Promise<string> {
  const { default: middleware } = await import("../../middleware")
  const response = middleware(new Request(new URL(path, "https://frontend.example.com")))
  if (!response.headers.has("x-middleware-rewrite")) {
    expect(response.headers.get("x-middleware-next")).toBe("1")
  }
  return response.headers.get("x-middleware-rewrite") ?? "/index.html"
}

describe("deployment routing", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubEnv("VERCEL_ENV", "production")
    vi.stubEnv("VITE_API_URL", "backend.example.com/")
    vi.stubEnv("VERCEL_RELATED_PROJECTS", "")
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  test.each(gitPaths)("forwards %s to the production backend", async (path) => {
    expect(await rewrite(path)).toBe(`https://backend.example.com${path}`)
  })

  test.each(["/", "/gitedge/gitedge", "/gitedge/gitedge/src/branch/main", "/login", "/owner/repoXgit/info/refs"])(
    "allows the SPA fallback for %s",
    async (path) => {
      expect(await rewrite(path)).toBe("/index.html")
    },
  )

  test.each([
    [{ branch: "backend-branch.vercel.app" }, "backend-branch.vercel.app"],
    [
      { branch: "backend-branch.vercel.app", customEnvironment: "backend-staging.vercel.app" },
      "backend-staging.vercel.app",
    ],
  ])("uses the related preview backend %j", async (preview, host) => {
    vi.stubEnv("VERCEL_ENV", "preview")
    vi.stubEnv(
      "VERCEL_RELATED_PROJECTS",
      JSON.stringify([{ project: { name: "gitedge-backend" }, production: {}, preview }]),
    )

    expect(await rewrite(gitPaths[0])).toBe(`https://${host}${gitPaths[0]}`)
  })

  test("fails when production backend configuration is missing", async () => {
    vi.stubEnv("VITE_API_URL", "")
    await expect(rewrite(gitPaths[0])).rejects.toThrow("Missing VITE_API_URL")
  })

  test("fails when the related preview backend is missing", async () => {
    vi.stubEnv("VERCEL_ENV", "preview")
    await expect(rewrite(gitPaths[0])).rejects.toThrow("Could not resolve the preview URL")
  })

  test("uses the local backend for Vercel development", async () => {
    vi.stubEnv("VERCEL_ENV", "development")
    expect(await rewrite(gitPaths[0])).toBe(`http://localhost:8000${gitPaths[0]}`)
  })
})
