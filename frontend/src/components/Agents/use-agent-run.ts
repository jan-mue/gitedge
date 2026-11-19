import { HttpAgent, type Message } from "@ag-ui/client"
import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import {
  agentsEnvironmentsQueryKey,
  agentsMessagesQueryKey,
  agentsNotificationsQueryKey,
  agentsRunsQueryKey,
  agentsSessionsQueryKey,
} from "@/client/@tanstack/react-query.gen"
import { agentHeaders, agentsBase, type RunPublic } from "./api"
import { durableAgentStream } from "./durable-stream"

export type CommandLog = {
  commandId: string
  lines: Record<string, { stream: string; chunk: string; sequence: number }>
}

export const useAgentRun = (sessionId: string, run: RunPublic | undefined, history: Message[], ready: boolean) => {
  const query = useQueryClient()
  const initial = useRef(history)
  initial.current = history
  const [messages, setMessages] = useState<Message[]>([])
  const [logs, setLogs] = useState<Record<string, CommandLog>>({})
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [_retry, setRetry] = useState(0)
  const runId = run?.id
  const prompt = run?.prompt
  useEffect(() => {
    if (!runId || !ready) return
    let mounted = true
    let stopped = false
    setBusy(true)
    setError("")
    const client = new HttpAgent({
      url: `${agentsBase}/runs/${runId}/events`,
      threadId: sessionId,
      initialMessages: [...initial.current, { id: `user-${runId}`, role: "user", content: prompt ?? "" }],
      fetch: (url, request) => durableAgentStream(url, agentHeaders(), request.signal),
    })
    setMessages([...client.messages])
    client
      .runAgent(
        { runId },
        {
          onMessagesChanged: ({ messages }) => {
            if (mounted) setMessages([...messages])
          },
          onCustomEvent: ({ event }) => {
            if (!mounted || event.name !== "bash_output" || !event.value || typeof event.value !== "object") return
            const value = event.value as Record<string, unknown>
            if (
              typeof value.command_id !== "string" ||
              typeof value.chunk !== "string" ||
              typeof value.stream !== "string" ||
              typeof value.sequence !== "number"
            )
              return
            const { command_id: commandId, chunk, stream, sequence } = value
            setLogs((previous) => ({
              ...previous,
              [commandId]: {
                commandId,
                lines: { ...previous[commandId]?.lines, [`${stream}:${sequence}`]: { stream, chunk, sequence } },
              },
            }))
          },
          onRunErrorEvent: ({ event }) => {
            stopped = event.code === "AgentRunCancelledError"
          },
        },
      )
      .then(async () => {
        if (!mounted) return
        await Promise.all([
          query.invalidateQueries({ queryKey: agentsEnvironmentsQueryKey() }),
          query.invalidateQueries({ queryKey: agentsSessionsQueryKey() }),
          query.invalidateQueries({ queryKey: agentsMessagesQueryKey({ path: { session_id: sessionId } }) }),
          query.invalidateQueries({ queryKey: agentsRunsQueryKey({ path: { session_id: sessionId } }) }),
          query.invalidateQueries({ queryKey: agentsNotificationsQueryKey() }),
        ])
      })
      .catch((reason) => {
        if (mounted && !stopped) setError(reason instanceof Error ? reason.message : "Unable to connect to the agent")
        if (mounted) {
          query.invalidateQueries({ queryKey: agentsSessionsQueryKey() })
          query.invalidateQueries({ queryKey: agentsRunsQueryKey({ path: { session_id: sessionId } }) })
        }
      })
      .finally(() => {
        if (mounted) setBusy(false)
      })
    return () => {
      mounted = false
      client.abortRun()
    }
  }, [runId, prompt, sessionId, ready, query])
  return { messages, logs: Object.values(logs), busy, error, reconnect: () => setRetry((value) => value + 1) }
}
