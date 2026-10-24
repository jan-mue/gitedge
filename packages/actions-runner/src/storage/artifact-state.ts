import { join } from "node:path"
import { gunzipSync } from "node:zlib"
import { inside, readResponse, TRANSFER_LIMIT, writeFile } from "../runtime/files.ts"

/** Only artifacts cross job boundaries in an archive. Caches use the controller API. */
export class ArtifactState {
  private restoration: Promise<void> | undefined
  constructor(
    private readonly root: string,
    private readonly restoreUrl: string | undefined,
    private readonly signal: AbortSignal,
  ) {}
  restore(): Promise<void> {
    this.restoration ??= this.restoreOnce()
    return this.restoration
  }
  private async restoreOnce(): Promise<void> {
    if (!this.restoreUrl) return
    const response = await fetch(this.restoreUrl, {
      signal: AbortSignal.any([this.signal, AbortSignal.timeout(15000)]),
    })
    const compressed = await readResponse(response)
    const tar = gunzipSync(compressed, { maxOutputLength: TRANSFER_LIMIT + 1024 * 1024 })
    const files = await new Bun.Archive(tar).files()
    let size = 0
    for (const [path, file] of files) {
      const normalized = path.replace(/^\.\//, "")
      if (!normalized.startsWith("artifacts/")) continue
      size += file.size
      if (size > TRANSFER_LIMIT) throw new Error("Artifacts exceed 32 MiB")
      await writeFile(inside(join(this.root, "state"), normalized), file)
    }
  }
  async export(): Promise<void> {
    // A cancelled action may still have initiated a restore; do not export partial state.
    await this.restoration
    const directory = join(this.root, "state"),
      files: Record<string, Uint8Array> = {}
    let size = 0
    for await (const path of new Bun.Glob("artifacts/**/*").scan({
      cwd: directory,
      onlyFiles: true,
      followSymlinks: false,
    })) {
      const file = Bun.file(inside(directory, path))
      size += file.size
      if (size > TRANSFER_LIMIT) throw new Error("Artifacts exceed 32 MiB")
      files[path] = await file.bytes()
    }
    const archive = new Bun.Archive(files, { compress: "gzip" })
    const bytes = await archive.bytes()
    if (bytes.byteLength > TRANSFER_LIMIT) throw new Error("Artifact archive exceeds 32 MiB")
    await writeFile(join(this.root, "state.tar.gz"), bytes)
  }
}
