import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "vitest"
import type { CacheClient, CacheEntry } from "./src/storage/cache-client.ts"
import { StorageServer } from "./src/storage/server.ts"

class MemoryCache implements CacheClient {
  readonly entries = new Map<string, { entry: CacheEntry; bytes: Uint8Array }>()
  async lookup(key: string, version: string, restoreKeys: string[]) {
    const candidates = [...this.entries.values()].toReversed().filter(({ entry }) => entry.version === version)
    const exact = candidates.find(({ entry }) => entry.key === key)
    if (exact) return exact.entry
    for (const prefix of [key, ...restoreKeys]) {
      const found = candidates.find(({ entry }) => entry.key.startsWith(prefix))
      if (found) return found.entry
    }
    return null
  }
  async save(key: string, version: string, bytes: Uint8Array) {
    const entry: CacheEntry = { id: crypto.randomUUID(), key, version, size: bytes.byteLength }
    this.entries.set(entry.id, { entry, bytes })
    return entry
  }
  async download(id: string) {
    const stored = this.entries.get(id)
    if (!stored) throw new Error("Cache evicted")
    return stored.bytes
  }
}
function startStorage(
  root: string,
  run: string,
  job: string,
  cache: CacheClient,
  restoreArtifacts?: () => Promise<void>,
) {
  return StorageServer.start({ root, run, job, cache, restoreArtifacts })
}

test("cache requests never download artifact archives and reject unauthenticated access", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-lazy-state-"))
  const cache = new MemoryCache()
  await cache.save("restored", "v1", new TextEncoder().encode("portable cache"))
  let restores = 0
  const storage = await startStorage(root, "123", "build", cache, async () => {
    restores++
  })
  const url = `${storage.environment.ACTIONS_CACHE_URL}_apis/artifactcache/cache?keys=restored&version=v1`
  try {
    assert.equal((await fetch(url)).status, 403)
    const responses = await Promise.all(
      Array.from({ length: 4 }, () =>
        fetch(url, { headers: { authorization: `Bearer ${storage.environment.ACTIONS_RUNTIME_TOKEN}` } }),
      ),
    )
    assert.equal(restores, 0)
    for (const response of responses) {
      assert.equal(response.status, 200)
      const result = await response.json()
      assert.equal(await (await fetch(result.archiveLocation)).text(), "portable cache")
    }
  } finally {
    await storage.close()
    await rm(root, { recursive: true, force: true })
  }
})

test("cache protocol restores finalized entries across job servers and authenticates transfers", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-storage-"))
  const cache = new MemoryCache()
  let storage = await startStorage(root, "123", "build", cache)
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
    storage = await startStorage(root, "456", "verify", cache)
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
  const cache = new MemoryCache()
  const storage = await startStorage(root, "123", "build", cache)
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
  const cache = new MemoryCache()
  let storage = await startStorage(root, "123", "build", cache)
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
    storage = await startStorage(root, "456", "verify", cache)
    const restored = await (await call("cache?keys=example&version=v1")).json()
    assert.equal(restored.cacheKey, "example")
    assert.equal(await (await fetch(restored.archiveLocation)).text(), "portable cache")
    assert.equal((await call("caches", "POST", { key: "example", version: "v1" })).status, 409)
  } finally {
    await storage.close()
    await rm(root, { recursive: true, force: true })
  }
})
