import { join } from "node:path"
import { z } from "zod"
import { type Action, parseAction } from "../domain/workflow.ts"
import { inside, readJson } from "../runtime/files.ts"

export interface ResolvedAction {
  directory: string
  repositoryRoot: string
  repository: string
  reference: string
  definition: Action
}

export class ActionResolver {
  private manifest: Promise<Record<string, string>> | undefined

  constructor(
    private readonly workspace: string,
    private readonly prepared: string,
  ) {}

  async resolve(uses: string): Promise<ResolvedAction> {
    let directory: string
    let repositoryRoot: string
    let repository = ""
    let reference = ""
    if (uses.startsWith("./")) {
      repositoryRoot = this.workspace
      directory = inside(this.workspace, uses)
    } else {
      const match = uses.match(/^([\w.-]+\/[\w.-]+)(\/[\w./-]+)?@([^\s]+)$/)
      if (!match || match[2]?.split("/").includes("..")) throw new Error(`Unsupported action: ${uses}`)
      repository = match[1]
      reference = match[3]
      this.manifest ??= readJson(join(this.prepared, "manifest.json"), z.record(z.string(), z.string()))
      const tree = (await this.manifest)[`${repository}@${reference}`]
      if (!tree) throw new Error(`Action ${uses} is not prepared in this image; rebuild the image before dispatch`)
      repositoryRoot = inside(this.prepared, tree)
      directory = inside(repositoryRoot, `.${match[2] || ""}`)
    }
    for (const name of ["action.yml", "action.yaml"]) {
      const file = Bun.file(join(directory, name))
      if (await file.exists())
        return { directory, repositoryRoot, repository, reference, definition: parseAction(await file.text()) }
    }
    throw new Error(`Missing action metadata: ${uses}`)
  }
}
