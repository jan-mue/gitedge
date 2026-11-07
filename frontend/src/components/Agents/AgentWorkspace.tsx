import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import {
  Archive,
  KeyRound,
  Loader2,
  Menu,
  PanelRight,
  Pin,
  Plus,
  Search,
  Server,
  Settings,
  SquarePen,
} from "lucide-react"
import { useState } from "react"
import { Button, Dialog, DialogContent, DialogTitle, Input, SelectField } from "@/components/design-system"
import { AgentComposer, AgentConversation } from "./AgentConversation"
import { agentApi, type EnvironmentPublic, type SessionPublic } from "./api"
import { CredentialDialog } from "./CredentialDialog"
import { EnvironmentDialog } from "./EnvironmentDialog"

export const AgentWorkspace = () => {
  const navigate = useNavigate()
  const search = useSearch({ from: "/_layout/agents" })
  const query = useQueryClient()
  const [environmentId, setEnvironmentId] = useState("")
  const [model, setModel] = useState("")
  const [filter, setFilter] = useState("")
  const [environmentDialog, setEnvironmentDialog] = useState(false)
  const [editing, setEditing] = useState<EnvironmentPublic>()
  const [credentials, setCredentials] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [details, setDetails] = useState(false)
  const envs = useQuery({
    queryKey: ["agent-environments"],
    queryFn: () => agentApi<EnvironmentPublic[]>("/environments"),
  })
  const sessions = useQuery({
    queryKey: ["agent-sessions"],
    queryFn: () => agentApi<SessionPublic[]>("/sessions"),
    refetchInterval: 5000,
  })
  const models = useQuery({ queryKey: ["agent-models"], queryFn: () => agentApi<string[]>("/models") })
  const selected = sessions.data?.find((chat) => chat.id === search.session)
  const environment = envs.data?.find((env) => env.id === (selected?.environment_id || environmentId))
  const currentModel = model || models.data?.[0] || ""
  const select = (session?: string) => {
    navigate({ to: "/agents", search: session ? { session } : {} })
    setMobile(false)
  }
  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: string; pinned?: boolean; archived?: boolean }) =>
      agentApi(`/sessions/${id}`, body, "PATCH"),
    onSuccess: () => query.invalidateQueries({ queryKey: ["agent-sessions"] }),
  })
  const create = async (prompt: string) => {
    if (!environment) throw new Error("Choose an environment first")
    const chat = await agentApi<SessionPublic>("/sessions", {
      environment_id: environment.id,
      title: prompt.slice(0, 200),
      kind: environment.snapshot_id ? "coding" : "setup",
    })
    query.setQueryData<SessionPublic[]>(["agent-sessions"], (old) => [chat, ...(old ?? [])])
    await agentApi(`/sessions/${chat.id}/runs`, { request_id: crypto.randomUUID(), prompt, model: currentModel })
    select(chat.id)
    await query.invalidateQueries({ queryKey: ["agent-sessions"] })
  }
  const setup = useMutation({
    mutationFn: async () => {
      if (!environment) throw new Error("Choose an environment first")
      const chat = await agentApi<SessionPublic>("/sessions", {
        environment_id: environment.id,
        title: `Set up ${environment.name}`,
        kind: "setup",
      })
      await query.invalidateQueries({ queryKey: ["agent-sessions"] })
      select(chat.id)
    },
  })
  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-12 items-center justify-between px-4">
        <h1 className="font-semibold">Agents</h1>
        <SquarePen className="size-4 text-muted-foreground" />
      </div>
      <div className="px-3">
        <Button variant="agentChat" onClick={() => select()}>
          <Plus className="size-4" />
          New chat
        </Button>
        <div className="relative my-3">
          <Search className="pointer-events-none absolute left-2 top-2 size-4 text-muted-foreground" />
          <Input
            aria-label="Search chats"
            appearance="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Search chats…"
          />
        </div>
      </div>
      <div className="flex-1 space-y-5 overflow-auto px-2 py-2">
        {[true, false].map((pinned) => (
          <section key={String(pinned)}>
            <h2 className="mb-2 px-2 text-xs text-muted-foreground">{pinned ? "Pinned" : "Recents"}</h2>
            {sessions.data
              ?.filter((chat) => !!chat.pinned === pinned && chat.title.toLowerCase().includes(filter.toLowerCase()))
              .map((chat) => (
                <Button
                  key={chat.id}
                  variant="agentChat"
                  aria-pressed={selected?.id === chat.id}
                  onClick={() => select(chat.id)}
                >
                  {chat.kind === "setup" && <Server className="size-4 text-muted-foreground" />}
                  <span className="flex-1 truncate">{chat.title}</span>
                  {chat.active_run && <Loader2 className="size-3 animate-spin text-primary" />}
                </Button>
              ))}
          </section>
        ))}
      </div>
      <div className="space-y-1 border-t border-border p-2">
        <Button variant="agentChat" onClick={() => setCredentials(true)}>
          <KeyRound className="size-4 text-muted-foreground" />
          AI credentials
        </Button>
        <Button
          variant="agentChat"
          onClick={() => {
            setEditing(undefined)
            setEnvironmentDialog(true)
          }}
        >
          <Server className="size-4 text-muted-foreground" />
          New environment
        </Button>
      </div>
    </div>
  )
  return (
    <div className="flex h-[calc(100dvh-3rem)] min-h-0 overflow-hidden bg-background">
      <aside className="hidden w-72 shrink-0 border-r border-border bg-secondary md:block">{sidebar}</aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
          <div className="flex min-w-0 items-center gap-2">
            <Button
              variant="ghost"
              size="icon-sm"
              visibility="mobile"
              aria-label="Open chats"
              onClick={() => setMobile(true)}
            >
              <Menu className="size-4" />
            </Button>
            <span className="truncate text-sm font-medium">{selected?.title ?? "New chat"}</span>
          </div>
          <div className="flex items-center gap-1">
            {selected && (
              <>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={selected.pinned ? "Unpin chat" : "Pin chat"}
                  onClick={() => patch.mutate({ id: selected.id, pinned: !selected.pinned })}
                >
                  <Pin className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Archive chat"
                  disabled={!!selected.active_run}
                  onClick={() => {
                    patch.mutate({ id: selected.id, archived: true })
                    select()
                  }}
                >
                  <Archive className="size-4" />
                </Button>
              </>
            )}
            <Button variant="outline" size="compact" onClick={() => setDetails(!details)}>
              <PanelRight className="size-4" />
              Environment
            </Button>
          </div>
        </header>
        {(envs.error || sessions.error || patch.error || setup.error) && (
          <p role="alert" className="p-4 text-sm text-destructive">
            {envs.error?.message || sessions.error?.message || patch.error?.message || setup.error?.message}
          </p>
        )}
        <datalist id="agent-model-options">
          {models.data?.map((value) => (
            <option key={value} value={value} />
          ))}
        </datalist>
        {selected ? (
          <AgentConversation key={selected.id} session={selected} model={currentModel} onModelChange={setModel} />
        ) : (
          <>
            <div className="flex flex-1 flex-col items-center justify-center gap-5 px-4">
              <SquarePen className="size-8 text-muted-foreground" />
              <h2 className="text-2xl font-semibold">What should we build?</h2>
              <p className="max-w-md text-center text-sm text-muted-foreground">
                Choose a prepared environment or set up your repositories for cloud coding.
              </p>
              <div className="w-full max-w-md">
                <SelectField
                  aria-label="Environment"
                  value={environmentId}
                  onValueChange={setEnvironmentId}
                  options={(envs.data ?? []).map((env) => ({
                    value: env.id,
                    label: `${env.name}${env.snapshot_id ? "" : " · setup required"}`,
                  }))}
                />
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setEditing(undefined)
                  setEnvironmentDialog(true)
                }}
              >
                <Plus className="size-4" />
                New environment
              </Button>
            </div>
            <div className="mx-auto w-full max-w-3xl px-4 pb-6">
              <AgentComposer model={currentModel} onModelChange={setModel} onSend={create} pending={false} />
            </div>
          </>
        )}
      </main>
      {details && (
        <aside className="w-72 shrink-0 space-y-5 overflow-auto border-l border-border bg-secondary p-4 max-lg:absolute max-lg:inset-y-12 max-lg:right-0 max-lg:z-20">
          <h2 className="font-medium">Environment</h2>
          {environment ? (
            <>
              <div>
                <p className="text-sm font-medium">{environment.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {environment.snapshot_id ? "Ready for coding chats" : "Setup required"}
                </p>
              </div>
              <ul className="space-y-2 text-sm">
                {environment.repositories?.map((repository) => (
                  <li key={repository}>{repository}</li>
                ))}
              </ul>
              <Button
                variant="outline"
                fullWidth
                onClick={() => {
                  setEditing(environment)
                  setEnvironmentDialog(true)
                }}
              >
                <Settings className="size-4" />
                Edit environment
              </Button>
              <Button variant="outline" fullWidth onClick={() => setup.mutate()}>
                Open setup chat
              </Button>
              <p className="text-xs text-muted-foreground">
                Each coding chat starts from the prepared environment and keeps its own changes.
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">Choose an environment to view its repositories and setup.</p>
          )}
        </aside>
      )}
      <EnvironmentDialog
        open={environmentDialog}
        onOpenChange={setEnvironmentDialog}
        environment={editing}
        onSaved={(value) => {
          setEnvironmentId(value.id)
          setDetails(true)
        }}
      />
      <CredentialDialog open={credentials} onOpenChange={setCredentials} />
      <Dialog open={mobile} onOpenChange={setMobile}>
        <DialogContent appearance="compact">
          <DialogTitle>Chats</DialogTitle>
          <div className="h-[70dvh]">{sidebar}</div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
