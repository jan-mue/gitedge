import { test } from "bun:test"
import assert from "node:assert/strict"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { launch } from "./launch.mjs"

test("Bun launcher exports state and publishes its completion marker before callback", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-launch-"))
  let delivered = 0
  const server = Bun.serve({
    port: 0,
    hostname: "127.0.0.1",
    async fetch() {
      assert.equal(await readFile(join(root, "exit-code"), "utf8"), "0")
      assert.equal(JSON.parse(await readFile(join(root, "result.json"), "utf8")).status, "success")
      delivered++
      return Response.json({ status: "accepted" })
    },
  })
  try {
    const { code, result } = await launch(
      {
        workflow: "jobs:\n  test:\n    steps:\n      - run: echo hello\n",
        job: "test",
        timeout_seconds: 10,
        dispatched_at_ms: Date.now(),
        env: { GITHUB_RUN_ID: "1" },
        complete_url: `http://127.0.0.1:${server.port}`,
      },
      { root },
    )
    assert.equal(code, 0)
    assert.equal(delivered, 1)
    assert.ok(result.startup_ms >= 0)
    assert.ok((await readFile(join(root, "state.tar.gz"))).length > 0)
  } finally {
    server.stop(true)
    await rm(root, { recursive: true, force: true })
  }
})

test("a job deadline kills its process and still exports a failed result", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-timeout-"))
  try {
    const { code } = await launch(
      {
        workflow: "jobs:\n  test:\n    steps:\n      - run: sleep 30\n",
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
