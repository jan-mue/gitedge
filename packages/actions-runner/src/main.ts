#!/usr/bin/env bun
import { inflateSync } from "node:zlib"
import { jobSchema } from "./domain/job.ts"
import { launch } from "./job-lifecycle.ts"
import { TRANSFER_LIMIT } from "./runtime/files.ts"

async function main(): Promise<void> {
  process.umask(0o077)
  const root = Bun.env.GITEDGE_JOB_ROOT || "/gitedge",
    encoded = Bun.env.GITEDGE_JOB
  const descriptor = encoded
    ? Bun.env.GITEDGE_JOB_ENCODING === "deflate"
      ? inflateSync(Buffer.from(encoded, "base64"), { maxOutputLength: TRANSFER_LIMIT }).toString()
      : encoded
    : await Bun.file(`${root}/job.json`).text()
  if (!encoded) await Bun.file(`${root}/job.json`).delete()
  const input = jobSchema.parse(JSON.parse(descriptor)),
    restoreUrl = Bun.env.GITEDGE_RESTORE_URL || input.restore_url
  for (const key of ["GITEDGE_JOB", "GITEDGE_JOB_ENCODING", "GITEDGE_RESTORE_URL", "GITEDGE_JOB_ROOT"])
    delete Bun.env[key]
  const controller = new AbortController()
  process.once("SIGTERM", () => controller.abort())
  process.once("SIGINT", () => controller.abort())
  process.exitCode = (await launch(input, { root, restoreUrl, signal: controller.signal })).code
}

if (import.meta.main) void main()
