import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { expect, test } from "vitest"
import { ActionResolver } from "../../../actions-runner/src/actions/resolver.ts"
import { jobSchema, type LogEntry } from "../../../actions-runner/src/domain/job.ts"
import { COMMAND_FILE_BYTES, CommandFiles, OutputCommands } from "../../../actions-runner/src/runtime/commands.ts"
import { JobEnvironment } from "../../../actions-runner/src/runtime/environment.ts"
import { existingInside, Workspace } from "../../../actions-runner/src/runtime/files.ts"
import { JobLog, JobLogger } from "../../../actions-runner/src/runtime/logger.ts"
import { JobReporter } from "../../../actions-runner/src/runtime/reporter.ts"
import { manifestFixture } from "./test-helpers.ts"

const input = async () =>
  jobSchema.parse(
    await manifestFixture({
      workflow: "on: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n",
      job: "test",
    }),
  )

test("action directories and metadata cannot follow symlinks outside the repository", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-paths-"))
  try {
    const source = join(root, "source")
    const outside = join(root, "outside")
    await mkdir(source)
    await mkdir(outside)
    await writeFile(join(outside, "action.yml"), "name: Outside\nruns:\n  using: node24\n  main: main.js\n")
    await symlink(outside, join(source, "action"))
    const resolver = new ActionResolver(source, root)
    await expect(resolver.resolve("./action")).rejects.toThrow("Path escapes its workspace")
    await expect(existingInside(source, "../outside")).rejects.toThrow("Path escapes its workspace")
    await mkdir(join(source, "metadata"))
    await symlink(join(outside, "action.yml"), join(source, "metadata", "action.yml"))
    await expect(resolver.resolve("./metadata")).rejects.toThrow("Path escapes its workspace")
    await symlink(source, join(source, "safe"))
    expect(await existingInside(source, "safe")).toBe(source)
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})

test("command files reject oversized and symlinked inputs before applying values", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-commands-"))
  try {
    const environment = new JobEnvironment(await input(), new Workspace(root), {})
    const files = new CommandFiles(join(root, "commands"))
    await files.prepare()
    await writeFile(files.paths.GITHUB_ENV, "x".repeat(COMMAND_FILE_BYTES + 1))
    await expect(files.collect(environment, {}, {})).rejects.toThrow("exceeds")
    await rm(files.paths.GITHUB_ENV)
    const outside = join(root, "outside")
    await writeFile(outside, "INJECTED=true")
    await symlink(outside, files.paths.GITHUB_ENV)
    await expect(files.collect(environment, {}, {})).rejects.toThrow()
    expect(environment.snapshot().INJECTED).toBeUndefined()
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})

test("oversized output lines are discarded explicitly and later output is retained", async () => {
  const entries: LogEntry[] = []
  const environment = new JobEnvironment(await input(), new Workspace("/tmp"), {})
  const logger = new JobLogger(
    {
      write: (entry) => {
        entries.push(entry)
      },
      close: async () => {},
    },
    [],
  )
  const commands = new OutputCommands(environment, logger, "test", {}, {})
  await commands.consume(
    new ReadableStream({
      start(controller) {
        for (let i = 0; i < 64; i++) controller.enqueue(Buffer.alloc(64 * 1024, "x"))
        controller.enqueue(Buffer.from("\nafter the long line\n"))
        controller.close()
      },
    }),
  )
  expect(entries.map((entry) => entry.msg)).toEqual(["[Output truncated: line exceeds 64 KiB]", "after the long line"])
})

test("total job log output is capped with one truncation notice", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-log-cap-"))
  try {
    const manifest = await input()
    const log = new JobLog(root, manifest.attempt, new JobReporter(manifest))
    for (let i = 0; i < 140; i++) await log.write({ msg: "x".repeat(64 * 1024) })
    await log.write({ msg: "discarded after cap" })
    await log.close()
    const output = await Bun.file(join(root, "log.jsonl")).text()
    expect(output.match(/Output truncated/g)).toHaveLength(1)
    expect(output).not.toContain("discarded after cap")
    expect(Buffer.byteLength(output)).toBeLessThan(9 * 1024 * 1024)
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})
