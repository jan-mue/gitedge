import { mkdtemp, rm, symlink } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { afterEach, beforeEach, describe, expect, test } from "vitest"
import { Workspace, writeFile } from "../runtime/files.ts"
import { ExpressionEngine } from "./evaluator.ts"

describe("asynchronous workflow expressions", () => {
  let workspace: Workspace
  beforeEach(async () => {
    workspace = new Workspace(await mkdtemp(join(tmpdir(), "gitedge-expressions-")))
    await workspace.prepare({})
  })
  afterEach(async () => {
    await rm(workspace.root, { recursive: true, force: true })
  })

  test("hashFiles evaluates dynamic patterns, exclusions, and multiple lazy calls", async () => {
    await writeFile(join(workspace.source, "a.txt"), "one")
    await writeFile(join(workspace.source, "b.txt"), "two")
    await writeFile(join(workspace.source, "ignored.txt"), "ignored")
    const engine = new ExpressionEngine(workspace)
    const expected = new Bun.CryptoHasher("sha256")
      .update(new Bun.CryptoHasher("sha256").update("one").digest())
      .update(new Bun.CryptoHasher("sha256").update("two").digest())
      .digest("hex")
    expect(
      await engine.interpolate(
        "${{ hashFiles(inputs.pattern, '!ignored.txt') }}",
        { inputs: { pattern: "*.txt" } },
        "success",
      ),
    ).toBe(expected)
    expect(await engine.interpolate("${{ hashFiles('a.txt') != hashFiles('b.txt') }}", {}, "success")).toBe(true)
    expect(await engine.interpolate("${{ false && hashFiles('../outside') }}", {}, "success")).toBe(false)
    expect(await engine.interpolate("${{ hashFiles('missing.*') }}", {}, "success")).toBe("")
  })

  test("hashFiles cannot read outside the checked-out workspace", async () => {
    await writeFile(join(workspace.root, "outside"), "private")
    await symlink(join(workspace.root, "outside"), join(workspace.source, "link"))
    await expect(workspace.hashFiles(["../outside"])).rejects.toThrow("escapes")
    // Symlinks are either excluded by Bun.Glob or rejected by the realpath boundary.
    const result = workspace.hashFiles(["link"])
    await expect(result.catch(() => "")).resolves.toBe("")
  })
})
