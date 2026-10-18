// Job-scoped cache and artifact protocols. This server exits with the job.

import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto"
import { mkdir, readFile, stat, unlink, writeFile } from "node:fs/promises"
import { createServer } from "node:http"
import { join } from "node:path"

const LIMIT = 32 * 1024 * 1024
async function body(request) {
  const parts = []
  let size = 0
  for await (const part of request) {
    size += part.length
    if (size > LIMIT) throw new Error("State transfer exceeds 32 MiB")
    parts.push(part)
  }
  return Buffer.concat(parts)
}
export async function startStorage(root, runId, jobId) {
  const secret = randomBytes(32).toString("base64url")
  const header = Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url")
  const payload = Buffer.from(
    JSON.stringify({
      scp: `Actions.Results:${runId}:${jobId}`,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 86400,
    }),
  ).toString("base64url")
  const unsigned = `${header}.${payload}`
  const token = `${unsigned}.${createHmac("sha256", secret).update(unsigned).digest("base64url")}`
  await mkdir(join(root, "cache"), { recursive: true })
  await mkdir(join(root, "artifacts", runId), { recursive: true })
  const indexPath = join(root, "cache", "index.json")
  let caches = []
  try {
    caches = JSON.parse(await readFile(indexPath, "utf8"))
  } catch (error) {
    if (error.code !== "ENOENT") throw error
  }
  const reservations = new Map()
  const pending = new Map()
  const files = new Map()
  let base
  function url(path, mode) {
    const id = createHash("sha256").update(path).digest("hex")
    files.set(id, path)
    return `${base}blob/${id}?${new URLSearchParams({ sig: secret, mode })}`
  }
  const server = createServer(async (request, response) => {
    try {
      const target = new URL(request.url, base)
      response.setHeader("x-ms-request-id", randomBytes(8).toString("hex"))
      response.setHeader("x-ms-version", "2023-11-03")
      const send = (value, status = 200) => {
        response.writeHead(status, { "Content-Type": "application/json" })
        response.end(JSON.stringify(value))
      }
      if (target.pathname.startsWith("/blob/")) {
        const supplied = Buffer.from(target.searchParams.get("sig") || "")
        const expected = Buffer.from(secret)
        if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected))
          return send({ error: "Unauthorized" }, 403)
        const path = files.get(target.pathname.split("/").pop())
        if (!path) return send({}, 404)
        if (request.method === "PUT" && target.searchParams.get("mode") === "write") {
          const raw = await body(request)
          const comp = target.searchParams.get("comp")?.toLowerCase()
          const entry = pending.get(path) || new Map()
          pending.set(path, entry)
          if (comp === "block") entry.set(target.searchParams.get("blockid"), raw)
          else if (comp === "blocklist") {
            const ids = [...raw.toString().matchAll(/<(?:Latest|Committed|Uncommitted)>(.*?)<\//g)].map(
              (match) => match[1],
            )
            const data = Buffer.concat(
              ids.map((id) => {
                if (!entry.has(id)) throw new Error("Missing upload block")
                return entry.get(id)
              }),
            )
            if (data.length > LIMIT) throw new Error("State transfer exceeds 32 MiB")
            await writeFile(path, data)
            pending.delete(path)
          } else await writeFile(path, raw)
          response.writeHead(201, { ETag: '"gitedge"' })
          return response.end()
        }
        if ((request.method === "GET" || request.method === "HEAD") && target.searchParams.get("mode") === "read") {
          const raw = await readFile(path)
          response.writeHead(200, {
            "Content-Length": raw.length,
            "Content-Type": "application/octet-stream",
            ETag: '"gitedge"',
          })
          return response.end(request.method === "HEAD" ? undefined : raw)
        }
        return send({}, 405)
      }
      if (request.headers.authorization !== `Bearer ${token}`) return send({ error: "Unauthorized" }, 403)
      // Official cache actions select this API on custom forge hostnames.
      if (target.pathname.startsWith("/_apis/artifactcache/")) {
        if (request.method === "GET" && target.pathname.endsWith("/cache")) {
          const keys = (target.searchParams.get("keys") || "").split(",")
          const version = target.searchParams.get("version")
          const candidates = caches.filter((entry) => entry.version === version).sort((a, b) => b.created - a.created)
          let found = candidates.find((entry) => entry.key === keys[0])
          for (const prefix of keys) {
            if (found) break
            found = candidates.find((entry) => entry.key.startsWith(prefix))
          }
          return found
            ? send({
                cacheKey: found.key,
                cacheVersion: found.version,
                archiveLocation: url(join(root, "cache", found.id), "read"),
              })
            : send({}, 204)
        }
        if (request.method === "POST" && target.pathname.endsWith("/caches")) {
          const { key, version } = JSON.parse((await body(request)).toString())
          if (
            caches.some((entry) => entry.key === key && entry.version === version) ||
            [...reservations.values()].some((entry) => entry.key === key && entry.version === version)
          )
            return send({ message: "Cache already exists" }, 409)
          const id = createHash("sha256").update(`${key}\0${version}`).digest("hex")
          const cacheId = reservations.size + 1
          reservations.set(String(cacheId), { key, version, id, chunks: new Map() })
          return send({ cacheId }, 201)
        }
        const entry = reservations.get(target.pathname.split("/").pop())
        if (!entry) return send({ message: "Cache reservation not found" }, 404)
        if (request.method === "PATCH") {
          const range = request.headers["content-range"]?.match(/^bytes (\d+)-(\d+)\/(?:\*|\d+)$/)
          if (!range) throw new Error("Invalid cache content range")
          const raw = await body(request)
          if (Number(range[2]) - Number(range[1]) + 1 !== raw.length || Number(range[2]) >= LIMIT)
            throw new Error("Invalid cache chunk size")
          entry.chunks.set(Number(range[1]), raw)
          return send({}, 204)
        }
        if (request.method === "POST") {
          const input = JSON.parse((await body(request)).toString())
          const chunks = [...entry.chunks.entries()].sort((a, b) => a[0] - b[0])
          let offset = 0
          for (const [start, raw] of chunks) {
            if (start !== offset) throw new Error("Non-contiguous cache upload")
            offset += raw.length
          }
          if (offset > LIMIT || offset !== Number(input.size)) throw new Error("Invalid cache upload size")
          await writeFile(join(root, "cache", entry.id), Buffer.concat(chunks.map(([, raw]) => raw)))
          caches.push({ key: entry.key, version: entry.version, id: entry.id, created: Date.now() })
          await writeFile(indexPath, JSON.stringify(caches))
          return send({}, 204)
        }
        return send({}, 405)
      }
      const input = JSON.parse((await body(request)).toString() || "{}")
      const get = (camel) => input[camel] ?? input[camel.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)]
      const method = target.pathname.split("/").pop()
      if (target.pathname.includes("CacheService/")) {
        const key = get("key")
        const version = get("version")
        if (method === "CreateCacheEntry") {
          const id = createHash("sha256").update(`${key}\0${version}`).digest("hex")
          const path = join(root, "cache", id)
          if (caches.some((entry) => entry.key === key && entry.version === version)) return send({ ok: false })
          pending.set(path, new Map())
          return send({ ok: true, signedUploadUrl: url(path, "write") })
        }
        if (method === "FinalizeCacheEntryUpload") {
          const id = createHash("sha256").update(`${key}\0${version}`).digest("hex")
          await stat(join(root, "cache", id))
          caches = caches.filter((entry) => entry.key !== key || entry.version !== version)
          caches.push({ key, version, id, created: Date.now() })
          await writeFile(indexPath, JSON.stringify(caches))
          return send({ ok: true, entryId: String(caches.length) })
        }
        if (method === "GetCacheEntryDownloadURL") {
          const keys = [key, ...(get("restoreKeys") || [])]
          const candidates = caches.filter((entry) => entry.version === version).sort((a, b) => b.created - a.created)
          let found = candidates.find((entry) => entry.key === key)
          for (const prefix of keys) {
            if (found) break
            found = candidates.find((entry) => entry.key.startsWith(prefix))
          }
          return send(
            found
              ? { ok: true, matchedKey: found.key, signedDownloadUrl: url(join(root, "cache", found.id), "read") }
              : { ok: false },
          )
        }
      }
      if (target.pathname.includes("ArtifactService/")) {
        const name = get("name")
        if (name && (name.includes("/") || name.includes("\\") || name === "." || name === ".."))
          throw new Error("Unsafe artifact name")
        const directory = name ? join(root, "artifacts", runId, name) : null
        const path = directory ? join(directory, `${name}.zip`) : null
        const id = name ? String(createHash("sha256").update(`${runId}:${name}`).digest().readUInt32BE()) : null
        if (method === "CreateArtifact") {
          await mkdir(directory, { recursive: true })
          return send({ ok: true, signedUploadUrl: url(path, "write") })
        }
        if (method === "FinalizeArtifact") {
          const metadata = {
            workflowRunBackendId: runId,
            workflowJobRunBackendId: jobId,
            databaseId: id,
            name,
            size: String((await stat(path)).size),
            createdAt: new Date().toISOString(),
          }
          await writeFile(join(directory, "metadata.json"), JSON.stringify(metadata))
          return send({ ok: true, artifactId: id })
        }
        if (method === "GetSignedArtifactURL") return send({ signedUrl: url(path, "read") })
        if (method === "DeleteArtifact") {
          await unlink(path)
          return send({ ok: true, artifactId: id })
        }
        if (method === "ListArtifacts") {
          const { readdir } = await import("node:fs/promises")
          const artifacts = []
          for (const entry of await readdir(join(root, "artifacts", runId), { withFileTypes: true })) {
            if (!entry.isDirectory()) continue
            try {
              const metadata = JSON.parse(
                await readFile(join(root, "artifacts", runId, entry.name, "metadata.json"), "utf8"),
              )
              if (
                (!get("nameFilter") || metadata.name === get("nameFilter")) &&
                (!get("idFilter") || metadata.databaseId === get("idFilter"))
              )
                artifacts.push(metadata)
            } catch (error) {
              if (error.code !== "ENOENT") throw error
            }
          }
          return send({ artifacts })
        }
      }
      send({ error: "Unsupported storage operation" }, 404)
    } catch (error) {
      response.writeHead(400, { "Content-Type": "application/json" })
      response.end(JSON.stringify({ error: error.message }))
    }
  })
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve))
  base = `http://127.0.0.1:${server.address().port}/`
  return {
    environment: {
      ACTIONS_RUNTIME_TOKEN: token,
      ACTIONS_RUNTIME_URL: base,
      ACTIONS_RESULTS_URL: base,
      ACTIONS_CACHE_URL: base,
      ACTIONS_CACHE_SERVICE_V2: "true",
    },
    close: () =>
      new Promise((resolve) => {
        server.close(resolve)
        server.closeAllConnections()
      }),
  }
}
