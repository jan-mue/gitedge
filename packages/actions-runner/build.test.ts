import assert from "node:assert/strict"
import { execFile } from "node:child_process"
import { chmod, mkdtemp, readFile, rm, stat } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"
import { promisify } from "node:util"
import { test } from "vitest"
import { manifestFixture } from "./test-helpers.ts"

test("distributed Bun bytecode launcher executes a job and keeps launch controls out of steps", async () => {
  const directory = await mkdtemp(join(tmpdir(), "gitedge-bundle-"))
  const execute = promisify(execFile)
  try {
    await execute("bun", ["build.ts"], {
      cwd: fileURLToPath(new URL(".", import.meta.url)),
      env: { ...process.env, GITEDGE_RUNNER_BUILD_OUTDIR: directory },
      timeout: 10000,
    })
    assert.ok((await stat(join(directory, "gitedge-launch.jsc"))).size > 0)
    const root = join(directory, "job")
    await chmod(join(directory, "gitedge-launch"), 0o755)
    await execute(join(directory, "gitedge-launch"), [], {
      env: {
        ...process.env,
        GITEDGE_JOB_ROOT: root,
        GITEDGE_JOB: JSON.stringify(
          await manifestFixture({
            workflow: `on: workflow_dispatch
defaults:
  run:
    shell: bun {0}
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          if (process.env.GITEDGE_JOB_ROOT || process.env.GITEDGE_JOB) throw new Error("Launch controls leaked")
          console.log("Bytecode launcher executed")
`,
            job: "test",
            env: { GITHUB_RUN_ID: "1" },
          }),
        ),
      },
      timeout: 10000,
    })
    assert.equal(await readFile(join(root, "exit-code"), "utf8"), "0")
    assert.match(await readFile(join(root, "log.jsonl"), "utf8"), /Bytecode launcher executed/)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})
