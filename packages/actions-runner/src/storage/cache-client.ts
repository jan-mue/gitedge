import { z } from "zod"
import { readResponse } from "../runtime/files.ts"

const cacheEntrySchema = z.object({
  id: z.string(),
  key: z.string(),
  version: z.string(),
  size: z.number().nonnegative(),
})
export type CacheEntry = z.infer<typeof cacheEntrySchema>
export interface CacheClient {
  lookup(key: string, version: string, restoreKeys: string[]): Promise<CacheEntry | null>
  save(key: string, version: string, bytes: Uint8Array): Promise<CacheEntry>
  download(id: string): Promise<Uint8Array>
}

/** A job capability scopes access to its repository; provider credentials never enter the VM. */
export class ControllerCacheClient implements CacheClient {
  constructor(
    private readonly endpoint: string | undefined,
    private readonly signal: AbortSignal,
  ) {}
  async lookup(key: string, version: string, restoreKeys: string[]): Promise<CacheEntry | null> {
    if (!this.endpoint) return null
    const url = this.url("lookup")
    url.searchParams.set("key", key)
    url.searchParams.set("version", version)
    for (const prefix of restoreKeys) url.searchParams.append("restore_keys", prefix)
    const response = await this.request(url)
    return cacheEntrySchema.nullable().parse(await response.json())
  }
  async save(key: string, version: string, bytes: Uint8Array): Promise<CacheEntry> {
    const url = this.url()
    url.searchParams.set("key", key)
    url.searchParams.set("version", version)
    const response = await this.request(url, { method: "POST", body: new Blob([new Uint8Array(bytes)]) })
    return cacheEntrySchema.parse(await response.json())
  }
  async download(id: string): Promise<Uint8Array> {
    return readResponse(await this.request(this.url(encodeURIComponent(id))))
  }
  private url(path = ""): URL {
    if (!this.endpoint) throw new Error("The controller did not configure a cache capability")
    const url = new URL(this.endpoint)
    if (path) url.pathname = `${url.pathname.replace(/\/$/, "")}/${path}`
    return url
  }
  private async request(url: URL, options: RequestInit = {}): Promise<Response> {
    const response = await fetch(url, {
      ...options,
      signal: AbortSignal.any([this.signal, AbortSignal.timeout(15000)]),
    })
    if (!response.ok) {
      await response.body?.cancel()
      throw new Error(`Cache service returned HTTP ${response.status}`)
    }
    return response
  }
}
