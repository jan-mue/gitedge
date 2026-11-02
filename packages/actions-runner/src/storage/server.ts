import { timingSafeEqual } from "node:crypto"
import { mkdir } from "node:fs/promises"
import { join } from "node:path"
import { z } from "zod"
import { errorMessage } from "../domain/job.ts"
import type { Environment } from "../domain/workflow.ts"
import { readResponse } from "../runtime/files.ts"
import { ArtifactStore } from "./artifacts.ts"
import { BlobTransfers } from "./transfers.ts"

export interface StorageOptions {
  root: string
  run: string
  job: string
  restoreArtifacts?: () => Promise<void>
}
export class StorageServer {
  private readonly token: string
  private readonly artifacts: ArtifactStore
  private readonly transfers: BlobTransfers
  private readonly server: Bun.Server<undefined>
  readonly environment: Environment

  private constructor(options: StorageOptions) {
    const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url")
    const payload = Buffer.from(
      JSON.stringify({
        scp: `Actions.Results:${encodeURIComponent(options.run)}:${encodeURIComponent(options.job)}`,
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 86400,
      }),
    ).toString("base64url")
    const unsigned = `${header}.${payload}`
    this.token = `${unsigned}.${new Bun.CryptoHasher("sha256", crypto.randomUUID()).update(unsigned).digest("base64url")}`
    this.transfers = new BlobTransfers(() => this.origin)
    this.artifacts = new ArtifactStore(
      join(options.root, "artifacts"),
      options.run,
      options.job,
      this.transfers,
      options.restoreArtifacts || (() => Promise.resolve()),
    )
    this.server = Bun.serve({ hostname: "127.0.0.1", port: 0, fetch: (request) => this.handle(request) })
    this.environment = {
      ACTIONS_RUNTIME_TOKEN: this.token,
      ACTIONS_RUNTIME_URL: this.origin,
      ACTIONS_RESULTS_URL: this.origin,
      ACTIONS_CACHE_URL: this.origin,
      ACTIONS_CACHE_SERVICE_V2: "true",
    }
  }

  static async start(options: StorageOptions): Promise<StorageServer> {
    await mkdir(join(options.root, "artifacts", options.run), { recursive: true })
    return new StorageServer(options)
  }

  get origin(): string {
    return `http://127.0.0.1:${this.server.port}/`
  }

  async close(): Promise<void> {
    await this.server.stop(true)
  }

  private async handle(request: Request): Promise<Response> {
    try {
      const url = new URL(request.url)
      let response: Response
      if (url.pathname.startsWith("/blob/")) response = await this.transfers.handle(request, url)
      else {
        const supplied = Buffer.from(request.headers.get("authorization") || "")
        const expected = Buffer.from(`Bearer ${this.token}`)
        if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected))
          return Response.json({ error: "Unauthorized" }, { status: 403 })
        {
          const raw = await readResponse(new Response(request.body))
          const input = z.record(z.string(), z.unknown()).parse(JSON.parse(new TextDecoder().decode(raw) || "{}"))
          const normalized = Object.fromEntries(
            Object.entries(input).map(([key, value]) => [
              key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase()),
              value,
            ]),
          )
          const method = url.pathname.split("/").pop() || ""
          response = url.pathname.includes("ArtifactService/")
            ? await this.artifact(method, normalized)
            : new Response(null, { status: 404 })
        }
      }
      response.headers.set("x-ms-request-id", crypto.randomUUID())
      response.headers.set("x-ms-version", "2023-11-03")
      return response
    } catch (error) {
      return Response.json({ error: errorMessage(error) }, { status: 400 })
    }
  }

  private async artifact(method: string, input: Record<string, unknown>): Promise<Response> {
    const fields = z
      .object({
        name: z.string().default(""),
        nameFilter: z.string().optional(),
        idFilter: z.union([z.string(), z.number()]).transform(String).optional(),
      })
      .parse(input)
    switch (method) {
      case "CreateArtifact":
        return Response.json({ ok: true, signedUploadUrl: await this.artifacts.create(fields.name) })
      case "FinalizeArtifact":
        return Response.json({ ok: true, artifactId: await this.artifacts.finalize(fields.name) })
      case "ListArtifacts":
        return Response.json({ artifacts: await this.artifacts.list(fields.nameFilter, fields.idFilter) })
      case "GetSignedArtifactURL":
        return Response.json({ signedUrl: await this.artifacts.download(fields.name) })
      case "DeleteArtifact":
        return Response.json({ ok: true, artifactId: await this.artifacts.delete(fields.name) })
      default:
        return new Response(null, { status: 404 })
    }
  }
}
