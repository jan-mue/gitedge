import { timingSafeEqual } from "node:crypto"
import { readResponse, TRANSFER_LIMIT, writeFile } from "../runtime/files.ts"

type Transfer = { mode: "write"; path: string } | { mode: "read"; load: () => Promise<Blob> }
/** Job-local signed URLs implement the block upload protocol used by the official SDKs. */
export class BlobTransfers {
  private readonly secret = crypto.randomUUID()
  private readonly transfers = new Map<string, Transfer>()
  private readonly pending = new Map<string, Map<string, Uint8Array>>()
  constructor(private readonly origin: () => string) {}
  upload(path: string): string {
    return this.issue({ mode: "write", path })
  }
  download(load: () => Promise<Blob>): string {
    return this.issue({ mode: "read", load })
  }
  private issue(transfer: Transfer): string {
    const id = crypto.randomUUID()
    this.transfers.set(id, transfer)
    return `${this.origin()}blob/${id}?sig=${this.secret}`
  }
  async handle(request: Request, url: URL): Promise<Response> {
    const supplied = Buffer.from(url.searchParams.get("sig") || ""),
      expected = Buffer.from(this.secret)
    if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected))
      return Response.json({ error: "Unauthorized" }, { status: 403 })
    const id = url.pathname.slice("/blob/".length),
      transfer = this.transfers.get(id)
    if (!transfer) return new Response(null, { status: 404 })
    if (transfer.mode === "read" && (request.method === "GET" || request.method === "HEAD")) {
      const blob = await transfer.load()
      return new Response(request.method === "HEAD" ? null : blob, {
        headers: { "content-length": String(blob.size), "content-type": "application/octet-stream", etag: '"gitedge"' },
      })
    }
    if (transfer.mode !== "write" || request.method !== "PUT") return new Response(null, { status: 405 })
    const raw = await readResponse(new Response(request.body)),
      operation = url.searchParams.get("comp")?.toLowerCase()
    const blocks = this.pending.get(id) || new Map<string, Uint8Array>()
    if (operation === "block") {
      blocks.set(url.searchParams.get("blockid") || "", raw)
      if ([...blocks.values()].reduce((size, part) => size + part.byteLength, 0) > TRANSFER_LIMIT) {
        this.pending.delete(id)
        throw new Error("Upload exceeds 32 MiB")
      }
      this.pending.set(id, blocks)
    } else if (operation === "blocklist") {
      const names = [...new TextDecoder().decode(raw).matchAll(/<(?:Latest|Committed|Uncommitted)>(.*?)<\//g)].map(
        (match) => match[1],
      )
      const parts = names.map((name) => {
        const part = blocks.get(name)
        if (!part) throw new Error("Missing upload block")
        return part
      })
      const blob = new Blob(parts.map((part) => new Uint8Array(part)))
      if (blob.size > TRANSFER_LIMIT) throw new Error("Upload exceeds 32 MiB")
      await writeFile(transfer.path, blob)
      this.pending.delete(id)
    } else await writeFile(transfer.path, raw)
    return new Response(null, { status: 201, headers: { etag: '"gitedge"' } })
  }
}
