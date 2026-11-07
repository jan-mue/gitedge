import { useEffect, useState } from "react"
import { z } from "zod"
import { ActionsService, type LogRecord } from "@/client"

const recordSchema = z.object({
  seq: z.number().int().positive(),
  msg: z.string().max(8192),
  step_id: z.string().nullable().optional(),
  status: z.enum(["queued", "running", "success", "failure", "cancelled", "skipped"]).nullable().optional(),
  end: z.boolean().default(true),
})

function bounded(records: LogRecord[]) {
  let size = 0
  let first = records.length
  while (first > 0 && records.length - first < 5000 && size + records[first - 1].msg.length <= 512 * 1024) {
    size += records[--first].msg.length
  }
  return { records: records.slice(first), truncated: first > 0 }
}

export function useJobLogs(owner: string, repo: string, runId: string, attemptId: string) {
  const [output, setOutput] = useState({ records: [] as LogRecord[], truncated: false })
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    const path = { owner, repo, run_id: runId, attempt_id: attemptId }
    let cursor = 0
    let finished = false
    let pending: LogRecord[] = []
    let truncated = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const flush = () => {
      clearTimeout(timer)
      timer = undefined
      if (signal.aborted || !pending.length) return
      const incoming = pending
      pending = []
      setOutput((previous) => {
        const next = bounded([...previous.records, ...incoming])
        return { records: next.records, truncated: previous.truncated || truncated || next.truncated }
      })
    }
    const append = (records: LogRecord[]) => {
      for (const record of records) {
        if (record.seq <= cursor) continue
        if (record.seq !== cursor + 1) throw new Error("Log stream has a sequence gap")
        cursor = record.seq
        pending.push(record)
      }
      const next = bounded(pending)
      pending = next.records
      truncated ||= next.truncated
      timer ??= setTimeout(flush, 100)
    }
    const connect = async () => {
      try {
        const { data } = await ActionsService.logHistory({ path, signal })
        append(data.records)
        flush()
        finished = data.complete
      } catch {
        if (!signal.aborted) setError("Unable to load job logs.")
        return
      }
      while (!signal.aborted && !finished) {
        try {
          const result = await ActionsService.logEvents({
            path,
            query: { after: cursor },
            headers: { "Last-Event-ID": cursor },
            signal,
            sseMaxRetryAttempts: 1,
            onSseEvent: ({ data, event }) => {
              if (signal.aborted) return
              if (event === "end") {
                finished = true
                setLive(false)
                return
              }
              if (event !== "log") return
              append([recordSchema.parse(data)])
              setLive(true)
              setError(null)
            },
            onSseError: () => {
              if (!signal.aborted) setError("Live output interrupted. Reconnecting…")
            },
          })
          for await (const _event of result.stream) {
            if (finished || signal.aborted) break
          }
          flush()
        } catch {
          if (!signal.aborted) setError("Live output interrupted. Reconnecting…")
        }
        if (!finished && !signal.aborted)
          await new Promise<void>((resolve) => {
            const done = () => {
              clearTimeout(retry)
              signal.removeEventListener("abort", done)
              resolve()
            }
            const retry = setTimeout(done, 500)
            signal.addEventListener("abort", done, { once: true })
          })
      }
    }
    void connect()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [owner, repo, runId, attemptId])

  return { ...output, error, live }
}
