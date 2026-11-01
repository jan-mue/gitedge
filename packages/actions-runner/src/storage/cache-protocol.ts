import { join } from "node:path"
import { z } from "zod"
import { readResponse, TRANSFER_LIMIT } from "../runtime/files.ts"
import type { CacheClient, CacheEntry } from "./cache-client.ts"
import type { BlobTransfers } from "./transfers.ts"

const identitySchema = z.object({ key: z.string().min(1).max(512), version: z.string().max(512) })
const finalizeSchema = z.object({ size: z.number().nonnegative().max(TRANSFER_LIMIT) })
interface Reservation {
  key: string
  version: string
  chunks: Map<number, Uint8Array>
  path: string
}
export class CacheProtocol {
  private readonly reservations = new Map<string, Reservation>()
  constructor(
    private readonly client: CacheClient,
    private readonly directory: string,
    private readonly transfers: BlobTransfers,
  ) {}
  private reserve(key: string, version: string): { id: string; entry: Reservation } {
    if ([...this.reservations.values()].some((entry) => entry.key === key && entry.version === version))
      throw new Error("Cache already reserved")
    const id = String(this.reservations.size + 1),
      entry: Reservation = { key, version, chunks: new Map(), path: join(this.directory, crypto.randomUUID()) }
    this.reservations.set(id, entry)
    return { id, entry }
  }
  private download(entry: CacheEntry): string {
    return this.transfers.download(async () => new Blob([new Uint8Array(await this.client.download(entry.id))]))
  }
  async legacy(request: Request, url: URL): Promise<Response> {
    if (request.method === "GET" && url.pathname.endsWith("/cache")) {
      const [key = "", ...prefixes] = (url.searchParams.get("keys") || "").split(",")
      const entry = await this.client.lookup(key, url.searchParams.get("version") || "", prefixes)
      return entry
        ? Response.json({ cacheKey: entry.key, cacheVersion: entry.version, archiveLocation: this.download(entry) })
        : new Response(null, { status: 204 })
    }
    if (request.method === "POST" && url.pathname.endsWith("/caches")) {
      const { key, version } = identitySchema.parse(await request.json())
      const existing = await this.client.lookup(key, version, [])
      if (
        existing?.key === key ||
        [...this.reservations.values()].some((entry) => entry.key === key && entry.version === version)
      )
        return Response.json({ message: "Cache already exists" }, { status: 409 })
      const { id } = this.reserve(key, version)
      return Response.json({ cacheId: Number(id) }, { status: 201 })
    }
    const id = url.pathname.split("/").pop() || "",
      entry = this.reservations.get(id)
    if (!entry) return Response.json({ message: "Cache reservation not found" }, { status: 404 })
    if (request.method === "PATCH") {
      const range = request.headers.get("content-range")?.match(/^bytes (\d+)-(\d+)\/(?:\*|\d+)$/),
        raw = await readResponse(new Response(request.body))
      if (!range || Number(range[2]) - Number(range[1]) + 1 !== raw.byteLength || Number(range[2]) >= TRANSFER_LIMIT)
        throw new Error("Invalid cache content range")
      entry.chunks.set(Number(range[1]), raw)
      if ([...entry.chunks.values()].reduce((size, chunk) => size + chunk.byteLength, 0) > TRANSFER_LIMIT)
        throw new Error("Cache exceeds 32 MiB")
      return new Response(null, { status: 204 })
    }
    if (request.method === "POST") {
      const { size } = finalizeSchema.parse(await request.json())
      let offset = 0
      const chunks = [...entry.chunks.entries()].sort(([a], [b]) => a - b)
      for (const [start, raw] of chunks) {
        if (start !== offset) throw new Error("Non-contiguous cache upload")
        offset += raw.byteLength
      }
      if (offset !== size || offset > TRANSFER_LIMIT) throw new Error("Invalid cache size")
      await this.client.save(
        entry.key,
        entry.version,
        new Uint8Array(await new Blob(chunks.map(([, raw]) => new Uint8Array(raw))).arrayBuffer()),
      )
      entry.chunks.clear()
      return new Response(null, { status: 204 })
    }
    return new Response(null, { status: 405 })
  }
  async twirp(method: string, input: Record<string, unknown>): Promise<Response> {
    const { key, version } = identitySchema.parse(input)
    switch (method) {
      case "CreateCacheEntry": {
        const existing = await this.client.lookup(key, version, [])
        if (existing?.key === key) return Response.json({ ok: false })
        const { entry } = this.reserve(key, version)
        return Response.json({ ok: true, signedUploadUrl: this.transfers.upload(entry.path) })
      }
      case "FinalizeCacheEntryUpload": {
        const entry = [...this.reservations.values()].find((entry) => entry.key === key && entry.version === version)
        if (!entry || !(await Bun.file(entry.path).exists())) throw new Error("Cache upload is missing")
        const bytes = await Bun.file(entry.path).bytes()
        if (bytes.byteLength > TRANSFER_LIMIT) throw new Error("Cache exceeds 32 MiB")
        const result = await this.client.save(key, version, bytes)
        await Bun.file(entry.path).delete()
        return Response.json({ ok: true, entryId: result.id })
      }
      case "GetCacheEntryDownloadURL": {
        const restoreKeys = z.array(z.string()).default([]).parse(input.restoreKeys)
        const entry = await this.client.lookup(key, version, restoreKeys)
        return Response.json(
          entry ? { ok: true, matchedKey: entry.key, signedDownloadUrl: this.download(entry) } : { ok: false },
        )
      }
      default:
        return new Response(null, { status: 404 })
    }
  }
}
