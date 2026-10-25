import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { expect, test } from "vitest"
import { writeFile } from "../runtime/files.ts"
import { ArtifactState } from "./artifact-state.ts"
import { StorageServer } from "./server.ts"

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

test("artifact protocol accepts optional metadata and persists ZIP content with escaped signed URLs", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-artifact-"))
  const storage = await StorageServer.start({ root, run: "123", job: "build:0" })
  try {
    const payload = storage.environment.ACTIONS_RUNTIME_TOKEN?.split(".")[1]
    assert.ok(payload)
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString())
    assert.deepEqual(claims.scp.split(":"), ["Actions.Results", "123", "build%3A0"])
    const call = async (method: string, data: Record<string, unknown>) =>
      (
        await fetch(
          `${storage.environment.ACTIONS_RESULTS_URL}twirp/github.actions.results.api.v1.ArtifactService/${method}`,
          {
            method: "POST",
            headers: { authorization: `Bearer ${storage.environment.ACTIONS_RUNTIME_TOKEN}` },
            body: JSON.stringify(data),
          },
        )
      ).json()
    const created = await call("CreateArtifact", {
      workflow_run_backend_id: "123",
      name: "example",
      version: 4,
      mime_type: "application/zip",
    })
    await fetch(created.signedUploadUrl, { method: "PUT", body: "ZIP bytes" })
    const finalized = await call("FinalizeArtifact", { name: "example", size: "9" })
    assert.equal(finalized.ok, true)
    assert.equal(await readFile(join(root, "artifacts", "123", "example", "example.zip"), "utf8"), "ZIP bytes")
    const list = await call("ListArtifacts", { name_filter: "example" })
    assert.equal(list.artifacts.length, 1)
    const signed = await call("GetSignedArtifactURL", { name: "example" })
    assert.equal(await (await fetch(signed.signedUrl)).text(), "ZIP bytes")
  } finally {
    await storage.close()
    await rm(root, { recursive: true, force: true })
  }
})
