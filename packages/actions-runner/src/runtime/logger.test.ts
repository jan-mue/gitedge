import { mkdtemp, readdir, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { expect, test } from "vitest"
import { jobSchema } from "../domain/job.ts"
import { JobLog, JobLogger } from "./logger.ts"
import { JobReporter } from "./reporter.ts"

const identity = {
  id: "11111111-1111-4111-8111-111111111111",
  job_id: "job",
  generation: 1,
  fence: "22222222-2222-4222-8222-222222222222",
}

function reporter(url: string) {
  return new JobReporter(
    jobSchema.parse({
      version: 4,
      attempt: identity,
      report_url: url,
      report_token: "report-token",
      workflow: { name: "test" },
      job: {
        id: "job",
        key: "job",
        name: "Job",
        needs: [],
        matrix: {},
        strategy: {},
        timeoutSeconds: 60,
        continueOnError: false,
        config: { steps: [{ kind: "run", id: "test", run: "true" }] },
      },
    }),
  )
}

test("spooled segments survive an unacknowledged delivery and preserve order and masking", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-logs-"))
  let healthy = false
  const payloads: string[] = []
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      expect(request.headers.get("authorization")).toBe("Bearer report-token")
      const payload = await request.text()
      payloads.push(payload)
      const parsed = JSON.parse(payload)
      if (!healthy) return new Response(null, { status: 403 })
      return Response.json({ acked_seq: parsed.to_seq })
    },
  })
  const log = new JobLog(root, identity, reporter(`http://127.0.0.1:${server.port}`))
  const logger = new JobLogger(log, ["secret-value", "report-token"])
  logger.mask("dynamic-secret\nsecond-secret-line")
  try {
    await logger.emit(
      `${"x".repeat(4093)}secret-value${"🔑".repeat(35000)}dynamic-secret second-secret-line report-token`,
      "step",
    )
    await log.flush()
    expect((await readdir(join(root, "logs"))).length).toBeGreaterThan(0)
    healthy = true
    await log.close()
    expect(await readdir(join(root, "logs"))).toEqual([])
    expect(payloads[0]).toBe(payloads.find((_, index) => index > 0))
    const unique = [...new Map(payloads.map((payload) => [JSON.parse(payload).from_seq, payload])).values()]
    const records = unique.flatMap((payload) => JSON.parse(payload).records)
    expect(records.map((record) => record.seq)).toEqual(records.map((_, index) => index + 1))
    expect(records.map((record) => record.msg).join("")).toBe(`${"x".repeat(4093)}***${"🔑".repeat(35000)}*** *** ***`)
    expect(unique.every((payload) => new TextEncoder().encode(payload).byteLength < 256 * 1024)).toBe(true)
  } finally {
    await server.stop(true)
    await rm(root, { recursive: true, force: true })
  }
})

test("the periodic flush delivers logs while a job is still active", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-live-"))
  let acknowledge: (() => void) | undefined
  const delivered = new Promise<void>((resolve) => {
    acknowledge = resolve
  })
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      const payload = await request.json()
      acknowledge?.()
      return Response.json({ acked_seq: payload.to_seq })
    },
  })
  const log = new JobLog(root, identity, reporter(`http://127.0.0.1:${server.port}`))
  try {
    await log.write({ msg: "first live output" })
    await delivered
    expect(log.lastSequence).toBe(1)
    await log.close()
  } finally {
    await server.stop(true)
    await rm(root, { recursive: true, force: true })
  }
})
