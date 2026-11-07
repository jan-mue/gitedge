import type { Message } from "@ag-ui/client"
import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowUp, Loader2, Square, SquareTerminal, User } from "lucide-react"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Button, Input, Label, MarkdownText, Textarea } from "@/components/design-system"
import { agentApi, type RunPublic, type SessionPublic } from "./api"
import { useAgentRun } from "./use-agent-run"

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
  const send = useMutation({
    mutationFn: async (values: { prompt: string }) => {
      await onSend(values.prompt)
      form.reset()
    },
  })
  return (
    <form
      className="rounded-xl border border-border bg-secondary p-3 shadow-sm"
      onSubmit={form.handleSubmit((values) => send.mutate(values))}
    >
      <Label htmlFor="agent-message">Message agent</Label>
      <Textarea
        id="agent-message"
        {...form.register("prompt")}
        placeholder="Describe a task…"
        disabled={pending || send.isPending}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault()
            form.handleSubmit((values) => send.mutate(values))()
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
            disabled={!form.watch("prompt").trim() || pending || send.isPending || !model}
            aria-label="Send message"
          >
            <ArrowUp className="size-4" />
          </Button>
        )}
      </div>
      {(send.error || form.formState.errors.prompt) && (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {send.error?.message || form.formState.errors.prompt?.message}
        </p>
      )}
    </form>
  )
}

const MessageView = ({ message }: { message: Message }) => {
  const content = "content" in message ? message.content : undefined
  const text =
    typeof content === "string"
      ? content
      : Array.isArray(content)
        ? content.map((part) => ("text" in part ? part.text : "")).join("\n")
        : ""
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
    queryKey: ["agent-messages", session.id],
    queryFn: () => agentApi<Message[]>(`/sessions/${session.id}/messages`),
    staleTime: Infinity,
  })
  const turns = useQuery({
    queryKey: ["agent-runs", session.id],
    queryFn: () => agentApi<RunPublic[]>(`/sessions/${session.id}/runs`),
    refetchInterval: 5000,
  })
  const lastFinished = turns.data
    ?.filter((turn) => turn.status !== "pending" && turn.status !== "running")
    .slice(-1)[0]?.id
  useEffect(() => {
    if (lastFinished) query.invalidateQueries({ queryKey: ["agent-messages", session.id] })
  }, [lastFinished, query, session.id])
  const active = turns.data?.find((turn) => turn.status === "pending" || turn.status === "running")
  const live = useAgentRun(session.id, active, history.data ?? [], !history.isPending && !history.isFetching)
  const submit = async (prompt: string) => {
    await agentApi(`/sessions/${session.id}/runs`, { request_id: crypto.randomUUID(), prompt, model })
    await query.invalidateQueries({ queryKey: ["agent-runs", session.id] })
    await query.invalidateQueries({ queryKey: ["agent-sessions"] })
  }
  const cancel = useMutation({
    mutationFn: () => agentApi(`/runs/${active?.id}/cancel`, {}),
    onSuccess: () => query.invalidateQueries({ queryKey: ["agent-runs", session.id] }),
  })
  const messages = live.messages.length > 0 ? live.messages : (history.data ?? [])
  return (
    <>
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-7 px-4 py-8">
          {session.kind === "setup" && (
            <div className="mb-8 text-center">
              <SquareTerminal className="mx-auto mb-3 size-8 text-muted-foreground" />
              <h2 className="text-xl font-semibold">Environment setup</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Get the repositories and dependencies ready for cloud coding chats.
              </p>
            </div>
          )}
          {history.isPending && <p className="text-sm text-muted-foreground">Loading conversation…</p>}
          {messages.map((message) => (
            <MessageView key={message.id} message={message} />
          ))}
          {(active || live.busy) && (
            <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              {active?.status === "pending" ? "Preparing cloud workspace…" : "Agent is working…"}
            </p>
          )}
          {Object.values(live.logs).map((log) => (
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
          {turns.data
            ?.filter((turn) => turn.status === "failed" || turn.status === "cancelled")
            .map((turn) => (
              <p key={turn.id} className="text-sm text-muted-foreground">
                {turn.status === "cancelled" ? "Run stopped" : `Run failed: ${turn.error ?? "Unknown error"}`}
              </p>
            ))}
          {(history.error || turns.error || live.error || cancel.error) && (
            <div role="alert" className="space-y-2 text-sm text-destructive">
              <p>{history.error?.message || turns.error?.message || live.error || cancel.error?.message}</p>
              {active && (
                <Button variant="outline" onClick={live.reconnect}>
                  Reconnect
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="mx-auto w-full max-w-3xl px-4 pb-6 pt-2">
        <AgentComposer
          model={model}
          onModelChange={onModelChange}
          onSend={submit}
          pending={!!active || live.busy}
          onStop={() => cancel.mutate()}
        />
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Cloud runs continue when you close this page. Ctrl/⌘ + Enter to send.
        </p>
      </div>
    </>
  )
}
