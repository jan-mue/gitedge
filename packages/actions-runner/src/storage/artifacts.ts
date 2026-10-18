import { join } from "node:path"
import { z } from "zod"
import { inside, readJson, writeFile } from "../runtime/files.ts"
import type { BlobTransfers } from "./transfers.ts"

const metadataSchema = z.object({
  workflowRunBackendId: z.string(),
  workflowJobRunBackendId: z.string(),
  databaseId: z.string(),
  name: z.string(),
  size: z.string(),
  createdAt: z.string(),
})
export type ArtifactMetadata = z.infer<typeof metadataSchema>
export class ArtifactStore {
  private restoration: Promise<void> | undefined
  private readonly directory: string
  constructor(
    root: string,
    private readonly run: string,
    private readonly job: string,
    private readonly transfers: BlobTransfers,
    private readonly restore: () => Promise<void>,
  ) {
    this.directory = inside(root, run)
  }
  private async ready(): Promise<void> {
    this.restoration ??= this.restore()
    await this.restoration
  }
  private paths(name: string): { file: string; metadata: string } {
    if (!name || name === "." || name === ".." || /[/\\\0]/.test(name)) throw new Error("Unsafe artifact name")
    const directory = inside(this.directory, name)
    return { file: join(directory, `${name}.zip`), metadata: join(directory, "metadata.json") }
  }
  async create(name: string): Promise<string> {
    await this.ready()
    const paths = this.paths(name)
    if (await Bun.file(paths.metadata).exists()) throw new Error(`Artifact ${name} already exists`)
    return this.transfers.upload(paths.file)
  }
  async finalize(name: string): Promise<string> {
    await this.ready()
    const paths = this.paths(name),
      file = Bun.file(paths.file)
    if (!(await file.exists())) throw new Error("Artifact upload is missing")
    const id = String(
      new DataView(new Bun.CryptoHasher("sha256").update(`${this.run}:${name}`).digest().buffer).getUint32(0),
    )
    const metadata: ArtifactMetadata = {
      workflowRunBackendId: this.run,
      workflowJobRunBackendId: this.job,
      databaseId: id,
      name,
      size: String(file.size),
      createdAt: new Date().toISOString(),
    }
    await writeFile(paths.metadata, JSON.stringify(metadata))
    return id
  }
  async list(name?: string, id?: string): Promise<ArtifactMetadata[]> {
    await this.ready()
    const artifacts: ArtifactMetadata[] = []
    for await (const path of new Bun.Glob("*/metadata.json").scan({
      cwd: this.directory,
      onlyFiles: true,
      throwErrorOnBrokenSymlink: true,
    })) {
      const metadata = await readJson(inside(this.directory, path), metadataSchema)
      if ((!name || metadata.name === name) && (!id || metadata.databaseId === id)) artifacts.push(metadata)
    }
    return artifacts
  }
  async download(name: string): Promise<string> {
    await this.ready()
    const paths = this.paths(name)
    return this.transfers.download(async () => {
      const file = Bun.file(paths.file)
      if (!(await file.exists())) throw new Error("Artifact is missing")
      return file
    })
  }
  async delete(name: string): Promise<string> {
    await this.ready()
    const paths = this.paths(name),
      metadata = await readJson(paths.metadata, metadataSchema)
    await Promise.all([Bun.file(paths.file).delete(), Bun.file(paths.metadata).delete()])
    return metadata.databaseId
  }
}
