import { useState } from "react"
import type { ActionJob } from "@/client"
import { client } from "@/client/client.gen"
import { Button, LogViewer } from "@/components/design-system"
import type { LogSection } from "@/components/design-system/log-viewer"
import { useJobLogs } from "./useJobLogs"

export const JobLogs = ({
  owner,
  repo,
  runId,
  job,
}: {
  owner: string
  repo: string
  runId: string
  job: ActionJob
}) => {
  if (!job.attempt_id)
    return <LogViewer sections={(job.steps ?? []).map((step) => ({ ...step, status: step.status ?? "queued" }))} />
  return (
    <AttemptLogs key={job.attempt_id} owner={owner} repo={repo} runId={runId} job={job} attemptId={job.attempt_id} />
  )
}

const AttemptLogs = ({
  owner,
  repo,
  runId,
  job,
  attemptId,
}: {
  owner: string
  repo: string
  runId: string
  job: ActionJob
  attemptId: string
}) => {
  const { records, truncated, error, live } = useJobLogs(owner, repo, runId, attemptId)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState(false)
  const log = records.map((record) => record.msg + (record.end ? "\n" : "")).join("")
  const sections: LogSection[] = (job.steps ?? []).map((step) => {
    const output = records.filter((record) => record.step_id === step.id)
    return {
      ...step,
      status:
        [...output].reverse().find((record) => record.status)?.status ||
        (output.length && step.status === "queued" ? "running" : step.status) ||
        "queued",
      log: output.map((record) => record.msg + (record.end ? "\n" : "")).join(""),
    }
  })
  const download = async () => {
    setDownloading(true)
    setDownloadError(false)
    try {
      const { data } = await client.get<{ 200: ReadableStream<Uint8Array> }, unknown, true>({
        url: "/api/v1/repositories/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt_id}/logs/download",
        path: { owner, repo, run_id: runId, attempt_id: attemptId },
        parseAs: "stream",
        security: [{ scheme: "bearer", type: "http" }],
        throwOnError: true,
      })
      const url = URL.createObjectURL(await new Response(data).blob())
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `${job.name.replace(/[^\w-]/g, "_")}.log`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch {
      setDownloadError(true)
    } finally {
      setDownloading(false)
    }
  }
  return (
    <>
      <div className="flex items-center justify-between gap-3 border-b px-4 py-2 text-xs text-muted-foreground">
        <span role="status">{error || (live ? "Live output" : "Job output")}</span>
        <Button variant="link" size="text" loading={downloading} onClick={download}>
          Download log
        </Button>
      </div>
      {downloadError && (
        <p role="alert" className="p-3 text-sm text-destructive">
          Unable to download the log.
        </p>
      )}
      <LogViewer sections={sections} log={log} truncated={truncated} />
    </>
  )
}
