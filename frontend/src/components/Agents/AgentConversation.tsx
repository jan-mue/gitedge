import type { Message } from "@ag-ui/client"
import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowUp, Loader2, Square, SquareTerminal, User } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import {
  agentsCancelRunMutation,
  agentsMessagesOptions,
  agentsMessagesQueryKey,
  agentsRunsOptions,
  agentsRunsQueryKey,
  agentsSessionsQueryKey,
  agentsSubmitMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, Input, Label, MarkdownText, Textarea } from "@/components/design-system"
import { extractErrorMessage } from "@/utils"
import type { RunPublic, SessionPublic } from "./api"
import { type CommandLog, useAgentRun } from "./use-agent-run"

const promptSchema = z.object({ prompt: z.string().trim().min(1).max(100000) })
export const AgentComposer = ({
  model,
  onModelChange,
  onSend,
  pending,
  onStop,
}: {
  model: string
  onModelChange: (value: string) => void
  onSend: (prompt: string) => Promise<unknown>
  pending: boolean
  onStop?: () => void
}) => {
  const form = useForm<{ prompt: string }>({ resolver: zodResolver(promptSchema), defaultValues: { prompt: "" } })
  const [sending, setSending] = useState(false)
  const [error, setError] = useState("")
  const send = async (values: { prompt: string }) => {
    setSending(true)
    setError("")
    try {
      await onSend(values.prompt)
      form.reset()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to send message")
    } finally {
      setSending(false)
    }
  }
  return (
    <form className="rounded-xl border border-border bg-secondary p-3 shadow-sm" onSubmit={form.handleSubmit(send)}>
      <Label htmlFor="agent-message">Message agent</Label>
      <Textarea
        id="agent-message"
        {...form.register("prompt")}
        placeholder="Describe a task…"
        disabled={pending || sending}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault()
            form.handleSubmit(send)()
          }
        }}
      />
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <Label htmlFor="agent-model">Model</Label>
          <Input
            id="agent-model"
            appearance="compact"
            value={model}
            onChange={(event) => onModelChange(event.target.value)}
            placeholder="provider:model"
            list="agent-model-options"
          />
        </div>
        {pending && onStop ? (
          <Button type="button" variant="outline" size="icon" aria-label="Stop agent" onClick={onStop}>
            <Square className="size-4" />
          </Button>
        ) : (
          <Button
            type="submit"
            size="icon"
            disabled={!form.watch("prompt").trim() || pending || sending || !model}
            aria-label="Send message"
          >
            <ArrowUp className="size-4" />
          </Button>
        )}
      </div>
      {(error || form.formState.errors.prompt) && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error || form.formState.errors.prompt?.message}
        </p>
      )}
    </form>
  )
}

const messageText = (message: Message) => {
  const content = "content" in message ? message.content : undefined
  if (typeof content === "string") return content
  if (!Array.isArray(content)) return ""
  return content.map((part) => ("text" in part ? part.text : "")).join("\n")
}

const MessageView = ({ message }: { message: Message }) => {
  const text = messageText(message)
  if (message.role === "tool")
    return (
      <details className="rounded-lg border border-border p-3 text-sm">
        <summary className="cursor-pointer text-muted-foreground">Tool result</summary>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{text}</pre>
      </details>
    )
  return (
    <article className="space-y-3" aria-label={`${message.role} message`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        {message.role === "user" ? (
          <User className="size-4 text-muted-foreground" />
        ) : (
          <SquareTerminal className="size-4 text-primary" />
        )}
        {message.role === "user" ? "You" : "Agent"}
      </div>
      {text && <MarkdownText>{text}</MarkdownText>}
      {"toolCalls" in message &&
        message.toolCalls?.map((call) => (
          <details key={call.id} className="rounded-lg border border-border bg-secondary p-3 text-sm">
            <summary className="cursor-pointer font-mono">{call.function.name}</summary>
            <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">{call.function.arguments}</pre>
          </details>
        ))}
    </article>
  )
}

const SetupHeader = () => (
  <div className="mb-8 text-center">
    <SquareTerminal className="mx-auto mb-3 size-8 text-muted-foreground" />
    <h2 className="text-xl font-semibold">Environment setup</h2>
    <p className="mt-2 text-sm text-muted-foreground">
      Get the repositories and dependencies ready for cloud coding chats.
    </p>
  </div>
)

const MessageList = ({ messages, loading }: { messages: Message[]; loading: boolean }) => (
  <>
    {loading && <p className="text-sm text-muted-foreground">Loading conversation…</p>}
    {messages.map((message) => (
      <MessageView key={message.id} message={message} />
    ))}
  </>
)

const RunStatus = ({ active, busy }: { active?: RunPublic; busy: boolean }) => {
  if (!active && !busy) return null
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" />
      {active?.status === "pending" ? "Preparing cloud workspace…" : "Agent is working…"}
    </p>
  )
}

const CommandLogs = ({ logs }: { logs: CommandLog[] }) => (
  <>
    {logs.map((log) => (
      <details key={log.commandId} className="rounded-lg border border-border p-3">
        <summary className="cursor-pointer text-sm">
          <SquareTerminal className="mr-2 inline size-4" />
          Command output
        </summary>
        <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs">
          {Object.values(log.lines).map((line, index) => (
            <span
              key={`${line.stream}:${line.sequence}:${index}`}
              className={line.stream === "stderr" ? "text-warning" : undefined}
            >
              {line.chunk}
            </span>
          ))}
        </pre>
      </details>
    ))}
  </>
)

const RunFailures = ({ turns }: { turns?: RunPublic[] }) => (
  <>
    {turns
      ?.filter((turn) => turn.status === "failed" || turn.status === "cancelled")
      .map((turn) => (
        <p key={turn.id} className="text-sm text-muted-foreground">
          {turn.status === "cancelled" ? "Run stopped" : `Run failed: ${turn.error ?? "Unknown error"}`}
        </p>
      ))}
  </>
)

const ConversationError = ({
  message,
  active,
  onReconnect,
}: {
  message: string
  active: boolean
  onReconnect: () => void
}) => {
  if (!message) return null
  return (
    <div role="alert" className="space-y-2 text-sm text-destructive">
      <p>{message}</p>
      {active && (
        <Button variant="outline" onClick={onReconnect}>
          Reconnect
        </Button>
      )}
    </div>
  )
}

export const AgentConversation = ({
  session,
  model,
  onModelChange,
}: {
  session: SessionPublic
  model: string
  onModelChange: (value: string) => void
}) => {
  const query = useQueryClient()
  const history = useQuery({
    ...agentsMessagesOptions({ path: { session_id: session.id } }),
    staleTime: Infinity,
  })
  const turns = useQuery({
    ...agentsRunsOptions({ path: { session_id: session.id } }),
    refetchInterval: 5000,
  })
  const lastFinished = turns.data
    ?.filter((turn) => turn.status !== "pending" && turn.status !== "running")
    .slice(-1)[0]?.id
  useEffect(() => {
    if (lastFinished)
      query.invalidateQueries({ queryKey: agentsMessagesQueryKey({ path: { session_id: session.id } }) })
  }, [lastFinished, query, session.id])
  const active = turns.data?.find((turn) => turn.status === "pending" || turn.status === "running")
  const historyMessages = (history.data ?? []) as unknown as Message[]
  const live = useAgentRun(session.id, active, historyMessages, !history.isPending && !history.isFetching)
  const submitRun = useMutation({ ...agentsSubmitMutation() })
  const submit = async (prompt: string) => {
    await submitRun.mutateAsync({
      path: { session_id: session.id },
      body: { request_id: crypto.randomUUID(), prompt, model },
    })
    await query.invalidateQueries({ queryKey: agentsRunsQueryKey({ path: { session_id: session.id } }) })
    await query.invalidateQueries({ queryKey: agentsSessionsQueryKey() })
  }
  const cancel = useMutation({
    ...agentsCancelRunMutation(),
    onSuccess: () => query.invalidateQueries({ queryKey: agentsRunsQueryKey({ path: { session_id: session.id } }) }),
  })
  const messages = live.messages.length > 0 ? live.messages : historyMessages
  const error =
    (history.error ? extractErrorMessage(history.error) : "") ||
    (turns.error ? extractErrorMessage(turns.error) : "") ||
    live.error ||
    (cancel.error ? extractErrorMessage(cancel.error) : "")
  return (
    <>
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-7 px-4 py-8">
          {session.kind === "setup" && <SetupHeader />}
          <MessageList messages={messages} loading={history.isPending} />
          <RunStatus active={active} busy={live.busy} />
          <CommandLogs logs={live.logs} />
          <RunFailures turns={turns.data} />
          <ConversationError message={error} active={!!active} onReconnect={live.reconnect} />
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-6 pt-2">
        <AgentComposer
          model={model}
          onModelChange={onModelChange}
          onSend={submit}
          pending={!!active || live.busy}
          onStop={() => active && cancel.mutate({ path: { run_id: active.id } })}
        />
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Cloud runs continue when you close this page. Ctrl/⌘ + Enter to send.
        </p>
      </div>
    </>
  )
}
