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
import {
  agentsCreateSessionMutation,
  agentsEnvironmentsOptions,
  agentsModelsOptions,
  agentsSessionsOptions,
  agentsSessionsQueryKey,
  agentsSubmitMutation,
  agentsUpdateSessionMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, Dialog, DialogContent, DialogTitle, Input, SelectField } from "@/components/design-system"
import { extractErrorMessage } from "@/utils"
import { AgentComposer, AgentConversation } from "./AgentConversation"
import type { EnvironmentPublic, SessionPublic } from "./api"
import { CredentialDialog } from "./CredentialDialog"
import { EnvironmentDialog } from "./EnvironmentDialog"

const ChatSidebar = ({
  sessions,
  selected,
  filter,
  onFilterChange,
  onSelect,
  onCredentials,
  onNewEnvironment,
}: {
  sessions?: SessionPublic[]
  selected?: SessionPublic
  filter: string
  onFilterChange: (value: string) => void
  onSelect: (session?: string) => void
  onCredentials: () => void
  onNewEnvironment: () => void
}) => (
  <div className="flex h-full flex-col">
    <div className="flex h-12 items-center justify-between px-4">
      <h1 className="font-semibold">Agents</h1>
      <SquarePen className="size-4 text-muted-foreground" />
    </div>
    <div className="px-3">
      <Button variant="agentChat" onClick={() => onSelect()}>
        <Plus className="size-4" />
        New chat
      </Button>
      <div className="relative my-3">
        <Search className="pointer-events-none absolute left-2 top-2 size-4 text-muted-foreground" />
        <Input
          aria-label="Search chats"
          appearance="search"
          value={filter}
          onChange={(event) => onFilterChange(event.target.value)}
          placeholder="Search chats…"
        />
      </div>
    </div>
    <div className="flex-1 space-y-5 overflow-auto px-2 py-2">
      {[true, false].map((pinned) => (
        <section key={String(pinned)}>
          <h2 className="mb-2 px-2 text-xs text-muted-foreground">{pinned ? "Pinned" : "Recents"}</h2>
          {sessions
            ?.filter((chat) => !!chat.pinned === pinned && chat.title.toLowerCase().includes(filter.toLowerCase()))
            .map((chat) => (
              <Button
                key={chat.id}
                variant="agentChat"
                aria-pressed={selected?.id === chat.id}
                onClick={() => onSelect(chat.id)}
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
      <Button variant="agentChat" onClick={onCredentials}>
        <KeyRound className="size-4 text-muted-foreground" />
        AI credentials
      </Button>
      <Button variant="agentChat" onClick={onNewEnvironment}>
        <Server className="size-4 text-muted-foreground" />
        New environment
      </Button>
    </div>
  </div>
)

const EmptyWorkspace = ({
  environments,
  environmentId,
  onEnvironmentChange,
  onNewEnvironment,
  model,
  onModelChange,
  onSend,
}: {
  environments?: EnvironmentPublic[]
  environmentId: string
  onEnvironmentChange: (value: string) => void
  onNewEnvironment: () => void
  model: string
  onModelChange: (value: string) => void
  onSend: (prompt: string) => Promise<unknown>
}) => (
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
          onValueChange={onEnvironmentChange}
          options={(environments ?? []).map((env) => ({
            value: env.id,
            label: `${env.name}${env.snapshot_id ? "" : " · setup required"}`,
          }))}
        />
      </div>
      <Button variant="outline" onClick={onNewEnvironment}>
        <Plus className="size-4" />
        New environment
      </Button>
    </div>
    <div className="mx-auto w-full max-w-3xl px-4 pb-6">
      <AgentComposer model={model} onModelChange={onModelChange} onSend={onSend} pending={false} />
    </div>
  </>
)

const WorkspaceError = ({ error }: { error?: unknown }) => {
  if (!error) return null
  return (
    <p role="alert" className="p-4 text-sm text-destructive">
      {extractErrorMessage(error)}
    </p>
  )
}

const EnvironmentDetails = ({
  environment,
  onEdit,
  onSetup,
}: {
  environment?: EnvironmentPublic
  onEdit: () => void
  onSetup: () => void
}) => (
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
        <Button variant="outline" fullWidth onClick={onEdit}>
          <Settings className="size-4" />
          Edit environment
        </Button>
        <Button variant="outline" fullWidth onClick={onSetup}>
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
)

export const AgentWorkspace = () => {
  const navigate = useNavigate()
  const search = useSearch({ from: "/_layout/agents" })
  const query = useQueryClient()
  const [environmentId, setEnvironmentId] = useState("")
  const [model, setModel] = useState<string>()
  const [filter, setFilter] = useState("")
  const [environmentDialog, setEnvironmentDialog] = useState(false)
  const [editing, setEditing] = useState<EnvironmentPublic>()
  const [credentials, setCredentials] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [details, setDetails] = useState(false)
  const envs = useQuery(agentsEnvironmentsOptions())
  const sessions = useQuery({ ...agentsSessionsOptions(), refetchInterval: 5000 })
  const models = useQuery(agentsModelsOptions())
  const selected = sessions.data?.find((chat) => chat.id === search.session)
  const environment = envs.data?.find((env) => env.id === (selected?.environment_id || environmentId))
  const currentModel = model ?? models.data?.[0] ?? ""
  const select = (session?: string) => {
    navigate({ to: "/agents", search: session ? { session } : {} })
    setMobile(false)
  }
  const openNewEnvironment = () => {
    setEditing(undefined)
    setEnvironmentDialog(true)
  }
  const patch = useMutation({
    ...agentsUpdateSessionMutation(),
    onSuccess: () => query.invalidateQueries({ queryKey: agentsSessionsQueryKey() }),
  })
  const createSession = useMutation({ ...agentsCreateSessionMutation() })
  const submit = useMutation({ ...agentsSubmitMutation() })
  const create = async (prompt: string) => {
    if (!environment) throw new Error("Choose an environment first")
    const chat = await createSession.mutateAsync({
      body: {
        environment_id: environment.id,
        title: prompt.slice(0, 200),
        kind: environment.snapshot_id ? "coding" : "setup",
      },
    })
    query.setQueryData<SessionPublic[]>(agentsSessionsQueryKey(), (old) => [chat, ...(old ?? [])])
    await submit.mutateAsync({
      path: { session_id: chat.id },
      body: { request_id: crypto.randomUUID(), prompt, model: currentModel },
    })
    select(chat.id)
    await query.invalidateQueries({ queryKey: agentsSessionsQueryKey() })
  }
  const setup = useMutation({
    ...agentsCreateSessionMutation(),
    onSuccess: async (chat) => {
      await query.invalidateQueries({ queryKey: agentsSessionsQueryKey() })
      select(chat.id)
    },
  })
  const openSetup = () => {
    if (!environment) return
    setup.mutate({
      body: { environment_id: environment.id, title: `Set up ${environment.name}`, kind: "setup" },
    })
  }
  const sidebar = (
    <ChatSidebar
      sessions={sessions.data}
      selected={selected}
      filter={filter}
      onFilterChange={setFilter}
      onSelect={select}
      onCredentials={() => setCredentials(true)}
      onNewEnvironment={openNewEnvironment}
    />
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
                  onClick={() =>
                    patch.mutate({ path: { session_id: selected.id }, body: { pinned: !selected.pinned } })
                  }
                >
                  <Pin className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Archive chat"
                  disabled={!!selected.active_run}
                  onClick={() => {
                    patch.mutate({ path: { session_id: selected.id }, body: { archived: true } })
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
        <WorkspaceError error={envs.error ?? sessions.error ?? patch.error ?? setup.error} />
        <datalist id="agent-model-options">
          {models.data?.map((value) => (
            <option key={value} value={value} />
          ))}
        </datalist>
        {selected ? (
          <AgentConversation key={selected.id} session={selected} model={currentModel} onModelChange={setModel} />
        ) : (
          <EmptyWorkspace
            environments={envs.data}
            environmentId={environmentId}
            onEnvironmentChange={setEnvironmentId}
            onNewEnvironment={openNewEnvironment}
            model={currentModel}
            onModelChange={setModel}
            onSend={create}
          />
        )}
      </main>
      {details && (
        <EnvironmentDetails
          environment={environment}
          onEdit={() => {
            setEditing(environment)
            setEnvironmentDialog(true)
          }}
          onSetup={openSetup}
        />
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
