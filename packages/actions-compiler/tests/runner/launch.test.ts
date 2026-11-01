import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { createServer } from "node:http"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "vitest"
import { type LaunchOptions, launch as launchAgent } from "../../../actions-runner/src/job-lifecycle.ts"
import { manifestFixture, type WorkflowFixture } from "./test-helpers.ts"

async function launch(input: WorkflowFixture, options: LaunchOptions) {
  return launchAgent(await manifestFixture(input), options)
}

test("agent pushes ordered logs and artifacts before completing, without sandbox file inspection", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-launch-"))
  const operations: string[] = []
  let cursor = 0
  let report: { last_seq: number; result: { status: string } } | undefined
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      assert.equal(request.headers.get("authorization"), "Bearer job-report-token")
      const operation = new URL(request.url).pathname.split("/").pop() || ""
      operations.push(operation)
      if (operation === "logs") {
        const data = await request.json()
        assert.equal(data.from_seq, cursor + 1)
        cursor = data.to_seq
        return Response.json({ acked_seq: cursor })
      }
      if (operation === "complete") report = await request.json()
      return new Response(null, { status: 204 })
    },
  })
  try {
    const { code } = await launch(
      {
        workflow:
          "on: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hello\n",
        job: "test",
        timeout_seconds: 10,
        env: { GITHUB_RUN_ID: "1" },
        report_url: `http://127.0.0.1:${server.port}/attempt`,
        report_token: "job-report-token",
      },
      { root },
    )
    assert.equal(code, 0)
    assert.equal(operations[operations.length - 1], "complete")
    assert.ok(operations.includes("artifacts") && operations.includes("logs"))
    assert.equal(report?.last_seq, cursor)
    assert.equal(report?.result.status, "success")
    assert.equal(await Bun.file(join(root, "result.json")).exists(), false)
    assert.equal(await Bun.file(join(root, "exit-code")).exists(), false)
    assert.equal(await Bun.file(join(root, "log.jsonl")).exists(), false)
  } finally {
    await server.stop(true)
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
