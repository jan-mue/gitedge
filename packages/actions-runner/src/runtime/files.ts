import { constants } from "node:fs"
import { mkdir, open, realpath } from "node:fs/promises"
import { join, relative, resolve } from "node:path"
import { Minimatch } from "minimatch"
import type { z } from "zod"
import type { JsonValue } from "../domain/workflow.ts"

export const TRANSFER_LIMIT = 32 * 1024 * 1024

export async function writeFile(path: string, data: string | Uint8Array | Blob): Promise<void> {
  await Bun.write(path, data, { createPath: true })
}

export async function readText(path: string, limit = TRANSFER_LIMIT): Promise<string> {
  const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK)
  try {
    const stat = await file.stat()
    if (!stat.isFile()) throw new Error("Expected a regular file")
    if (stat.size > limit) throw new Error(`File exceeds ${limit} bytes`)
    const buffer = Buffer.alloc(limit + 1)
    let size = 0
    while (size <= limit) {
      const { bytesRead } = await file.read(buffer, size, buffer.length - size)
      if (!bytesRead) return buffer.subarray(0, size).toString()
      size += bytesRead
    }
    throw new Error(`File exceeds ${limit} bytes`)
  } finally {
    await file.close()
  }
}

export async function readJson<T extends z.ZodType>(path: string, schema: T): Promise<z.output<T>> {
  return schema.parse(await Bun.file(path).json())
}

export async function readResponse(response: Response, limit = TRANSFER_LIMIT): Promise<Uint8Array> {
  if (!response.ok) throw new Error(`Storage request failed: HTTP ${response.status}`)
  const parts: Uint8Array[] = []
  let size = 0
  if (!response.body) return new Uint8Array()
  for await (const chunk of response.body) {
    size += chunk.byteLength
    if (size > limit) throw new Error("Transfer exceeds 32 MiB")
    parts.push(chunk)
  }
  const result = new Uint8Array(size)
  let offset = 0
  for (const part of parts) {
    result.set(part, offset)
    offset += part.byteLength
  }
  return result
}

export function inside(root: string, path: string): string {
  const target = resolve(root, path)
  if (target !== resolve(root) && !target.startsWith(`${resolve(root)}/`)) throw new Error("Path escapes its workspace")
  return target
}

export async function existingInside(root: string, path: string): Promise<string> {
  const base = await realpath(root)
  return inside(base, await realpath(inside(base, path)))
}

export class Workspace {
  readonly source: string
  readonly temporary: string
  readonly state: string

  constructor(readonly root: string) {
    this.source = join(root, "source")
    this.temporary = join(root, "temp")
    this.state = join(root, "state")
  }

  async prepare(event: JsonValue): Promise<void> {
    await Promise.all([
      mkdir(this.source, { recursive: true }),
      mkdir(this.temporary, { recursive: true }),
      mkdir(this.state, { recursive: true }),
    ])
    await writeFile(join(this.root, "event.json"), JSON.stringify(event))
  }

  async hashFiles(patterns: readonly string[]): Promise<string> {
    const selected = new Set<string>()
    const rules = patterns.map((pattern) => {
      const exclude = pattern.startsWith("!")
      const glob = relative(this.source, inside(this.source, exclude ? pattern.slice(1) : pattern))
      return { exclude, matcher: new Minimatch(glob, { dot: true, nonegate: true, nocomment: true }) }
    })
    for await (const path of new Bun.Glob("**/*").scan({
      cwd: this.source,
      onlyFiles: true,
      dot: true,
      followSymlinks: false,
    })) {
      let included = false
      for (const rule of rules) if (rule.matcher.match(path)) included = !rule.exclude
      if (!included) continue
      const absolute = await existingInside(this.source, path)
      selected.add(absolute)
    }
    if (!selected.size) return ""
    const combined = new Bun.CryptoHasher("sha256")
    for (const path of [...selected].sort())
      combined.update(new Bun.CryptoHasher("sha256").update(await Bun.file(path).arrayBuffer()).digest())
    return combined.digest("hex")
  }
}
