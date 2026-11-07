import { HttpAgent, type Message } from "@ag-ui/client"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowUp, Plus, Server, SquarePen, Terminal } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { repositoriesListRepositoriesOptions } from "@/client/@tanstack/react-query.gen"
import { Button, ChoiceInput, Input, Label, SelectField, Textarea } from "@/components/design-system"
import { durableAgentStream } from "./durable-stream"

type Environment = { id: string; name: string; snapshot_id: string | null }
type Session = { id: string; title: string; kind: string; environment_id: string }
type Run = { id: string; status: string }
const base = `${import.meta.env.VITE_API_URL ?? ""}/api/v1/agents`
const headers = () => ({
  Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
  "Content-Type": "application/json",
})
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) throw new Error((await response.json()).detail ?? "Agent request failed")
  return response.json()
}

export const AgentWorkspace = () => {
  const query = useQueryClient()
  const [selected, setSelected] = useState<Session | null>(null)
  const [environment, setEnvironment] = useState("")
  const [prompt, setPrompt] = useState("")
  const [model, setModel] = useState("")
  const [name, setName] = useState("")
  const [repositories, setRepositories] = useState<string[]>([])
  const [setup, setSetup] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [answer, setAnswer] = useState("")
  const [logs, setLogs] = useState("")
  const agent = useRef<HttpAgent | null>(null)
  const repositoryList = useQuery(repositoriesListRepositoriesOptions())
  const envs = useQuery({ queryKey: ["agent-environments"], queryFn: () => api<Environment[]>("/environments") })
  const sessions = useQuery({ queryKey: ["agent-sessions"], queryFn: () => api<Session[]>("/sessions") })
  const models = useQuery({ queryKey: ["agent-models"], queryFn: () => api<string[]>("/models") })
  const history = useQuery({
    queryKey: ["agent-messages", selected?.id],
    queryFn: () => api<Message[]>(`/sessions/${selected?.id}/messages`),
    enabled: !!selected,
  })
  useEffect(() => () => agent.current?.abortRun(), [])
  const createEnvironment = async () => {
    setError("")
    try {
      const env = await api<Environment>("/environments", {
        name,
        repositories,
      })
      await query.invalidateQueries({ queryKey: ["agent-environments"] })
      setEnvironment(env.id)
      setSetup(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create environment")
    }
  }
  const send = async () => {
    if (!prompt.trim() || busy) return
    setBusy(true)
    setError("")
    setAnswer("")
    setLogs("")
    try {
      let chat = selected
      if (!chat) {
        const env = envs.data?.find((item) => item.id === environment)
        if (!env) throw new Error("Choose an environment first")
        chat = await api<Session>("/sessions", {
          environment_id: env.id,
          title: prompt.slice(0, 200),
          kind: env.snapshot_id ? "coding" : "setup",
        })
        setSelected(chat)
        await query.invalidateQueries({ queryKey: ["agent-sessions"] })
      }
      const run = await api<Run>(`/sessions/${chat.id}/runs`, {
        request_id: crypto.randomUUID(),
        prompt,
        model: model || models.data?.[0],
      })
      setPrompt("")
      const client = new HttpAgent({
        url: `${base}/runs/${run.id}/events`,
        threadId: chat.id,
        fetch: (url, init) => durableAgentStream(url, headers(), init.signal),
      })
      agent.current = client
      await client.runAgent(
        { runId: run.id },
        {
          onTextMessageContentEvent: ({ event }) => setAnswer((text) => text + event.delta),
          onCustomEvent: ({ event }) => {
            if (event.name === "bash_output") setLogs((text) => text + String(event.value.chunk))
          },
        },
      )
      await query.invalidateQueries({ queryKey: ["agent-environments"] })
      await query.invalidateQueries({ queryKey: ["agent-messages", chat.id] })
      setAnswer("")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Agent run failed")
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex min-h-[calc(100vh-3rem)] bg-background">
      <aside className="w-64 shrink-0 border-r border-border bg-secondary p-3 max-md:hidden">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="font-semibold">Agents</h1>
          <SquarePen className="size-4" />
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            setSelected(null)
            setAnswer("")
            setLogs("")
          }}
        >
          <Plus className="size-4" />
          New chat
        </Button>
        <h2 className="mt-6 mb-2 text-xs text-muted-foreground">Recents</h2>
        {sessions.data?.map((chat) => (
          <Button
            key={chat.id}
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setSelected(chat)
              setAnswer("")
              setLogs("")
            }}
          >
            {chat.kind === "setup" && <Server className="size-4" />}
            {chat.title}
          </Button>
        ))}
      </aside>
      <main className="mx-auto flex w-full max-w-4xl flex-col p-6">
        <header className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {selected?.kind === "setup" ? "Environment setup" : (selected?.title ?? "What should we build?")}
          </h2>
          <Button variant="outline" onClick={() => setSetup(!setup)}>
            New environment
          </Button>
        </header>
        {setup && (
          <div className="mb-6 space-y-3 rounded-lg border border-border p-4">
            <Label htmlFor="environment-name">Environment name</Label>
            <Input id="environment-name" value={name} onChange={(e) => setName(e.target.value)} />
            <fieldset className="space-y-2">
              <legend className="mb-2 text-sm">Repositories</legend>
              {repositoryList.data?.data.map((repository) => {
                const name = `${repository.owner}/${repository.name}`
                return (
                  <label key={name} htmlFor={`agent-repo-${name}`} className="flex items-center gap-2 text-sm">
                    <ChoiceInput
                      id={`agent-repo-${name}`}
                      type="checkbox"
                      checked={repositories.includes(name)}
                      onChange={(event) =>
                        setRepositories((previous) =>
                          event.target.checked ? [...previous, name] : previous.filter((value) => value !== name),
                        )
                      }
                    />
                    {name}
                  </label>
                )
              })}
              {repositoryList.data?.data.length === 0 && (
                <p className="text-sm text-muted-foreground">Create a repository to prepare your first environment.</p>
              )}
            </fieldset>
            <Button onClick={createEnvironment}>Create environment</Button>
          </div>
        )}
        {!selected && (
          <div className="space-y-4">
            <p className="text-muted-foreground">
              Prepare a repository environment in a setup chat, then fork its snapshot for coding tasks.
            </p>
            <SelectField
              aria-label="Environment"
              value={environment}
              onValueChange={setEnvironment}
              options={(envs.data ?? []).map((env) => ({
                value: env.id,
                label: `${env.name}${env.snapshot_id ? "" : " · setup required"}`,
              }))}
            />
          </div>
        )}
        {(error || envs.error) && (
          <p role="alert" className="my-4 text-destructive">
            {error || envs.error?.message}
          </p>
        )}
        <div className="my-6 flex-1 whitespace-pre-wrap text-sm" aria-live="polite">
          {history.data?.map((message) => (
            <div key={message.id} className="mb-4">
              <strong>{message.role}</strong>
              <p>{"content" in message && typeof message.content === "string" ? message.content : ""}</p>
            </div>
          ))}
          {answer || (busy ? "Starting cloud agent…" : "")}
        </div>
        {logs && (
          <details open className="mb-4 rounded-lg border border-border p-3">
            <summary className="flex items-center gap-2 text-sm">
              <Terminal className="size-4" />
              Command output
            </summary>
            <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap font-mono text-xs">{logs}</pre>
          </details>
        )}
        <div className="rounded-lg border border-border bg-secondary p-3">
          <Label htmlFor="agent-prompt">Message agent</Label>
          <Textarea
            id="agent-prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe a task…"
            disabled={busy}
          />
          <div className="mt-3 flex items-end justify-between gap-3">
            <SelectField
              aria-label="Model"
              value={model || models.data?.[0] || ""}
              onValueChange={setModel}
              options={(models.data ?? []).map((value) => ({ value, label: value }))}
            />
            <Button onClick={send} disabled={busy || !prompt.trim()} aria-label="Send message">
              <ArrowUp className="size-4" />
            </Button>
          </div>
        </div>
      </main>
    </div>
  )
}
