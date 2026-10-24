import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { createServer } from "node:http"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "vitest"
import { type LaunchOptions, launch as launchAgent } from "./src/job-lifecycle.ts"
import { manifestFixture, type WorkflowFixture } from "./test-helpers.ts"

async function launch(input: WorkflowFixture, options: LaunchOptions) {
  return launchAgent(await manifestFixture(input), options)
}

test("Bun launcher exports state and publishes its completion marker before callback", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-launch-"))
  let delivered = 0
  let callbackError: unknown
  const server = createServer(async (_request, response) => {
    try {
      assert.equal(await readFile(join(root, "exit-code"), "utf8"), "0")
      assert.equal(JSON.parse(await readFile(join(root, "result.json"), "utf8")).status, "success")
      delivered++
      response.end(JSON.stringify({ status: "accepted" }))
    } catch (error) {
      callbackError = error
      response.statusCode = 500
      response.end()
    }
  })
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()))
  const address = server.address()
  assert.ok(address && typeof address !== "string")
  try {
    const { code } = await launch(
      {
        workflow:
          "on: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hello\n",
        job: "test",
        timeout_seconds: 10,
        env: { GITHUB_RUN_ID: "1" },
        complete_url: `http://127.0.0.1:${address.port}`,
      },
      { root },
    )
    assert.equal(code, 0)
    assert.equal(delivered, 1)
    assert.equal(callbackError, undefined)
    assert.ok((await readFile(join(root, "state.tar.gz"))).length > 0)
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()))
    await rm(root, { recursive: true, force: true })
  }
})

test("a job deadline kills its process and still exports a failed result", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-timeout-"))
  try {
    const { code } = await launch(
      {
        workflow:
          "on: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: sleep 30\n",
        job: "test",
        timeout_seconds: 0.05,
        env: { GITHUB_RUN_ID: "1" },
      },
      { root },
    )
    assert.equal(code, 124)
    assert.equal(await readFile(join(root, "exit-code"), "utf8"), "124")
    assert.equal(JSON.parse(await readFile(join(root, "result.json"), "utf8")).status, "failure")
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})

test("shell-only jobs start and finish without requesting remote cache/artifact state", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-no-restore-"))
  let requests = 0
  const server = createServer((_request, response) => {
    requests++
    response.writeHead(503).end()
  })
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve))
  const address = server.address()
  assert.ok(address && typeof address !== "string")
  try {
    const { code } = await launch(
      {
        workflow:
          "on: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ready\n",
        job: "test",
        env: { GITHUB_RUN_ID: "1" },
      },
      { root, restoreUrl: `http://127.0.0.1:${address.port}` },
    )
    assert.equal(code, 0)
    assert.equal(requests, 0)
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()))
    await rm(root, { recursive: true, force: true })
  }
})
