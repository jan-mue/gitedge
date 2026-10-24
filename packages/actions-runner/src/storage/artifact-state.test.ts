import { mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { expect, test } from "vitest"
import { writeFile } from "../runtime/files.ts"
import { ArtifactState } from "./artifact-state.ts"

test("Bun archives hand artifacts between fresh jobs without transferring cache or source", async () => {
  const first = await mkdtemp(join(tmpdir(), "gitedge-artifacts-first-")),
    second = await mkdtemp(join(tmpdir(), "gitedge-artifacts-second-"))
  let server: Bun.Server<undefined> | undefined
  try {
    await writeFile(join(first, "state/artifacts/123/results/results.zip"), "artifact bytes")
    await writeFile(join(first, "state/cache/should-not-transfer"), "cache bytes")
    const signal = new AbortController().signal
    await new ArtifactState(first, undefined, signal).export()
    const archive = Bun.file(join(first, "state.tar.gz"))
    server = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response(archive) })
    const state = new ArtifactState(second, `http://127.0.0.1:${server.port}/`, signal)
    await Promise.all([state.restore(), state.restore()])
    expect(await Bun.file(join(second, "state/artifacts/123/results/results.zip")).text()).toBe("artifact bytes")
    expect(await Bun.file(join(second, "state/cache/should-not-transfer")).exists()).toBe(false)
    expect(await Bun.file(join(second, "source")).exists()).toBe(false)
  } finally {
    await server?.stop(true)
    await Promise.all([first, second].map((path) => rm(path, { recursive: true, force: true })))
  }
})

test("artifact restore rejects traversal entries and oversized decompressed archives", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-artifact-unsafe-"))
  const archive = await new Bun.Archive({ "artifacts/../../escape": "private" }, { compress: "gzip" }).blob()
  const server = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: () => new Response(archive) })
  try {
    await expect(
      new ArtifactState(root, `http://127.0.0.1:${server.port}/`, new AbortController().signal).restore(),
    ).rejects.toThrow()
    expect(await Bun.file(join(root, "escape")).exists()).toBe(false)
  } finally {
    await server.stop(true)
    await rm(root, { recursive: true, force: true })
  }
})
