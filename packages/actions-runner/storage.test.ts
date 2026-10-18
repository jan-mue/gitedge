import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "vitest"
import { startStorage } from "./storage.ts"

test("cache protocol restores finalized entries across job servers and authenticates transfers", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-storage-"))
  let storage = await startStorage(root, "123", "build")
  try {
    const call = async (method: string, data: Record<string, unknown>) => {
      const response = await fetch(
        `${storage.environment.ACTIONS_RESULTS_URL}twirp/github.actions.results.api.v1.CacheService/${method}`,
        {
          method: "POST",
          headers: { authorization: `Bearer ${storage.environment.ACTIONS_RUNTIME_TOKEN}` },
          body: JSON.stringify(data),
        },
      )
      assert.equal(response.status, 200)
      return response.json()
    }
    const created = await call("CreateCacheEntry", { key: "exact-key", version: "v1" })
    const upload = new URL(created.signedUploadUrl)
    upload.searchParams.set("comp", "block")
    upload.searchParams.set("blockid", "first")
    assert.equal((await fetch(upload, { method: "PUT", body: "portable " })).status, 201)
    upload.searchParams.set("blockid", "second")
    await fetch(upload, { method: "PUT", body: "cache" })
    upload.searchParams.set("comp", "blocklist")
    await fetch(upload, { method: "PUT", body: "<BlockList><Latest>first</Latest><Latest>second</Latest></BlockList>" })
    assert.equal((await call("FinalizeCacheEntryUpload", { key: "exact-key", version: "v1" })).ok, true)
    await storage.close()
    storage = await startStorage(root, "456", "verify")
    const restored = await call("GetCacheEntryDownloadURL", { key: "other", restoreKeys: ["exact-"], version: "v1" })
    assert.equal(restored.matchedKey, "exact-key")
    assert.equal(await (await fetch(restored.signedDownloadUrl)).text(), "portable cache")
    const unauthorized = new URL(restored.signedDownloadUrl)
    unauthorized.searchParams.delete("sig")
    assert.equal((await fetch(unauthorized)).status, 403)
    assert.equal((await call("GetCacheEntryDownloadURL", { key: "exact-key", version: "v2" })).ok, false)
  } finally {
    await storage.close()
    await rm(root, { recursive: true, force: true })
  }
})
test("artifact protocol accepts optional metadata and persists ZIP content with escaped signed URLs", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-artifact-"))
  const storage = await startStorage(root, "123", "build")
  try {
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

test("legacy cache protocol supports custom forge actions and ordered chunk commit", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-legacy-cache-"))
  let storage = await startStorage(root, "123", "build")
  try {
    const call = (
      path: string,
      method = "GET",
      data?: Record<string, unknown> | string,
      headers: Record<string, string> = {},
    ) =>
      fetch(`${storage.environment.ACTIONS_CACHE_URL}_apis/artifactcache/${path}`, {
        method,
        headers: { authorization: `Bearer ${storage.environment.ACTIONS_RUNTIME_TOKEN}`, ...headers },
        ...(data == null ? {} : { body: typeof data === "string" ? data : JSON.stringify(data) }),
      })
    assert.equal((await call("cache?keys=example&version=v1")).status, 204)
    const reserved = await (await call("caches", "POST", { key: "example", version: "v1" })).json()
    assert.equal(
      (await call(`caches/${reserved.cacheId}`, "PATCH", "cache", { "content-range": "bytes 9-13/*" })).status,
      204,
    )
    assert.equal(
      (await call(`caches/${reserved.cacheId}`, "PATCH", "portable ", { "content-range": "bytes 0-8/*" })).status,
      204,
    )
    assert.equal((await call(`caches/${reserved.cacheId}`, "POST", { size: 14 })).status, 204)
    await storage.close()
    storage = await startStorage(root, "456", "verify")
    const restored = await (await call("cache?keys=example&version=v1")).json()
    assert.equal(restored.cacheKey, "example")
    assert.equal(await (await fetch(restored.archiveLocation)).text(), "portable cache")
    assert.equal((await call("caches", "POST", { key: "example", version: "v1" })).status, 409)
  } finally {
    await storage.close()
    await rm(root, { recursive: true, force: true })
  }
})
