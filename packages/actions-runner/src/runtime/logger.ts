import { rm } from "node:fs/promises"
import { join } from "node:path"
import { z } from "zod"
import type { JobSpec, JobStatus, LogEntry, LogSink } from "../domain/job.ts"
import { writeFile } from "./files.ts"
import type { JobReporter } from "./reporter.ts"

interface LogRecord {
  seq: number
  msg: string
  step_id?: string
  status?: JobStatus
  end: boolean
}

const ackSchema = z.object({ acked_seq: z.number().int().nonnegative() })
const CHUNK_BYTES = 64 * 1024
const SPOOL_BYTES = 16 * 1024 * 1024

export class JobLog implements LogSink {
  private pending = Promise.resolve()
  private records: LogRecord[] = []
  private buffered = 0
  private spooled = 0
  private localBytes = 0
  private sequence = 0
  private readonly files: { path: string; to: number; size: number }[] = []
  private readonly timer: ReturnType<typeof setInterval>
  private timerBusy = false
  private failure: Error | undefined
  private deliveryError: unknown
  private readonly local: Bun.FileSink | undefined

  constructor(
    private readonly root: string,
    private readonly identity: JobSpec["attempt"],
    private readonly reporter: JobReporter,
  ) {
    if (!reporter.enabled) this.local = Bun.file(join(root, "log.jsonl")).writer()
    this.timer = setInterval(() => {
      if (this.timerBusy || this.failure) return
      this.timerBusy = true
      void this.flush()
        .catch((error) => {
          this.failure = error instanceof Error ? error : new Error(String(error))
        })
        .finally(() => {
          this.timerBusy = false
        })
    }, 500)
    this.timer.unref()
  }

  get lastSequence(): number {
    return this.sequence
  }

  write(entry: LogEntry): Promise<void> {
    return this.enqueue(async () => {
      const characters = Array.from(entry.msg)
      const count = Math.max(1, Math.ceil(characters.length / 4096))
      for (let part = 0; part < count; part++) {
        const record: LogRecord = {
          seq: ++this.sequence,
          end: part === count - 1,
          msg: characters.slice(part * 4096, (part + 1) * 4096).join(""),
          ...(entry.stepID?.[0] ? { step_id: entry.stepID[0] } : {}),
          ...(part === count - 1 && entry.stepResult ? { status: entry.stepResult } : {}),
        }
        if (this.local) {
          const raw = `${JSON.stringify({
            ...entry,
            msg: record.msg,
            attemptID: this.identity.id,
            jobID: this.identity.job_id,
            generation: this.identity.generation,
            fence: this.identity.fence,
          })}\n`
          this.localBytes += new TextEncoder().encode(raw).byteLength
          if (this.localBytes > SPOOL_BYTES) throw new Error("Local log exceeds 16 MiB")
          this.local.write(raw)
          continue
        }
        const size = new TextEncoder().encode(JSON.stringify(record)).byteLength + 1
        if (this.buffered + size > CHUNK_BYTES || this.records.length >= 512) {
          await this.seal()
          await this.deliver()
        }
        this.records.push(record)
        this.buffered += size
      }
    })
  }

  flush(): Promise<void> {
    return this.enqueue(async () => {
      if (this.local) {
        await this.local.flush()
        return
      }
      await this.seal()
      await this.deliver()
    })
  }

  async close(): Promise<void> {
    clearInterval(this.timer)
    await this.flush()
    if (this.local) await this.local.end()
    if (this.files.length) throw new Error("Job has unacknowledged log chunks", { cause: this.deliveryError })
  }

  private enqueue(task: () => Promise<void>): Promise<void> {
    if (this.failure) return Promise.reject(this.failure)
    this.pending = this.pending.then(task)
    return this.pending
  }

  private async seal(): Promise<void> {
    if (!this.records.length) return
    const from = this.records[0].seq
    const to = this.records[this.records.length - 1].seq
    const payload = JSON.stringify({ version: 1, ...this.identity, from_seq: from, to_seq: to, records: this.records })
    const size = new TextEncoder().encode(payload).byteLength
    if (this.spooled + size > SPOOL_BYTES) throw new Error("Unacknowledged logs exceed the 16 MiB spool limit")
    const path = join(this.root, "logs", `${from}.json`)
    await writeFile(path, payload)
    this.files.push({ path, to, size })
    this.spooled += size
    this.records = []
    this.buffered = 0
  }

  private async deliver(): Promise<void> {
    while (this.files.length) {
      const file = this.files[0]
      try {
        const response = await this.reporter.post("logs", await Bun.file(file.path).text())
        if (!response || ackSchema.parse(await response.json()).acked_seq !== file.to)
          throw new Error("Log acknowledgement has the wrong sequence")
      } catch (error) {
        this.deliveryError = error
        return
      }
      await rm(file.path)
      this.files.shift()
      this.spooled -= file.size
    }
  }
}

export class JobLogger {
  private readonly masks: Set<string>

  constructor(
    private readonly sink: LogSink,
    secrets: readonly string[],
  ) {
    this.masks = new Set()
    for (const secret of secrets) this.mask(secret)
  }

  mask(value: string): void {
    for (const part of [value, ...value.split(/\r?\n/)]) if (part) this.masks.add(part)
  }

  redact(value: string): string {
    let result = value
    for (const secret of [...this.masks].sort((a, b) => b.length - a.length)) result = result.split(secret).join("***")
    return result
  }

  async emit(message: string, step?: string, status?: JobStatus): Promise<void> {
    await this.sink.write({
      msg: this.redact(message),
      stepID: step ? [step] : [],
      ...(status ? { stepResult: status } : {}),
    })
  }
}
