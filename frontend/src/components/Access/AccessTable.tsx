import { ChevronLeft, ChevronRight, Search, Trash2 } from "lucide-react"
import { type Dispatch, type SetStateAction, useId, useState } from "react"
import {
  Alert,
  AlertDescription,
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FilterDropdown,
  Input,
  Label,
  SelectField,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/design-system"
import { AccessIdentity, type AccessPerson } from "./AccessIdentity"
import { type AccessRole, AddPeopleDialog } from "./AddPeopleDialog"

export interface AccessEntry extends AccessPerson {
  role: string
  protected?: boolean
  detail: string
}

export const AccessTable = ({
  target,
  scope,
  entries,
  roles,
  canManage = true,
  loading,
  error,
  retry,
  teams,
  repositoryOwner,
  onAdd,
  onRoleChange,
  onRemove,
}: {
  target: string
  scope: "repository" | "organization"
  entries: AccessEntry[]
  roles: AccessRole[]
  canManage?: boolean
  loading: boolean
  error: boolean
  retry: () => void
  teams?: AccessPerson[]
  repositoryOwner?: string
  onAdd: (people: AccessPerson[], role: string) => Promise<void>
  onRoleChange: (entry: AccessEntry, role: string) => Promise<void>
  onRemove: (entries: AccessEntry[]) => Promise<void>
}) => {
  const id = useId()
  const [query, setQuery] = useState("")
  const [kind, setKind] = useState("all")
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(0)
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState<AccessEntry[]>([])
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState("")
  const filtered = entries.filter(
    (entry) =>
      (kind === "all" || entry.kind === kind || entry.role === kind) &&
      `${entry.name} ${entry.displayName ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()),
  )
  const lastPage = Math.max(0, Math.ceil(filtered.length / 10) - 1)
  const currentPage = Math.min(page, lastPage)
  const visible = filtered.slice(currentPage * 10, currentPage * 10 + 10)
  const selectable = visible.filter((entry) => !entry.protected)
  const selection = entries.filter((entry) => selected.has(entry.id) && !entry.protected)
  const allSelected = selectable.length > 0 && selectable.every((entry) => selected.has(entry.id))
  const perform = async (action: () => Promise<void>) => {
    setBusy(true)
    setActionError("")
    try {
      await action()
    } catch {
      setActionError("Unable to update access. Refresh and try again.")
    } finally {
      setBusy(false)
    }
  }
  return (
    <section
      id={scope === "repository" ? "collaborators" : "members"}
      className="space-y-5"
      aria-label={scope === "repository" ? "Repository collaborators" : "Organization members"}
    >
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-lg font-semibold">Manage access</h3>
        {canManage && (
          <Button variant="repository" disabled={busy || loading || error} onClick={() => setAdding(true)}>
            Add people
          </Button>
        )}
      </div>
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}
      <div className="overflow-hidden rounded-md border border-border">
        <Table scrollLabel="Access management" aria-label="Access management">
          <AccessToolbar
            id={id}
            scope={scope}
            query={query}
            kind={kind}
            roles={roles}
            canManage={canManage}
            busy={busy}
            selectable={selectable}
            selected={selected}
            selection={selection}
            allSelected={allSelected}
            setSelected={setSelected}
            setRemoving={setRemoving}
            setKind={setKind}
            setQuery={setQuery}
            setPage={setPage}
          />
          <TableBody>
            {loading || error || !visible.length ? (
              <AccessStatus
                loading={loading}
                error={error}
                scope={scope}
                hasEntries={entries.length > 0}
                retry={retry}
              />
            ) : (
              visible.map((entry) => (
                <AccessTableEntry
                  key={entry.id}
                  entry={entry}
                  roles={roles}
                  canManage={canManage}
                  busy={busy}
                  selected={selected}
                  setSelected={setSelected}
                  setRemoving={setRemoving}
                  perform={perform}
                  onRoleChange={onRoleChange}
                />
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <nav aria-label="Access pagination" className="flex justify-center gap-3">
        <Button variant="quiet" disabled={currentPage === 0 || loading} onClick={() => setPage(currentPage - 1)}>
          <ChevronLeft aria-hidden="true" className="size-4" />
          Previous
        </Button>
        <span className="sr-only" role="status">
          Page {currentPage + 1} of {lastPage + 1}
        </span>
        <Button variant="quiet" disabled={currentPage === lastPage || loading} onClick={() => setPage(currentPage + 1)}>
          Next
          <ChevronRight aria-hidden="true" className="size-4" />
        </Button>
      </nav>
      {adding && (
        <AddPeopleDialog
          open
          onOpenChange={setAdding}
          target={target}
          scope={scope}
          existing={new Set(entries.map((entry) => entry.id))}
          roles={roles}
          teams={teams}
          repositoryOwner={repositoryOwner}
          onAdd={onAdd}
        />
      )}
      <Dialog
        open={removing.length > 0}
        onOpenChange={(open) => {
          if (!open && !busy) setRemoving([])
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove access?</DialogTitle>
            <DialogDescription>
              {removing.length === 1 ? removing[0]?.name : `${removing.length} selected people`} will lose{" "}
              {scope === "repository" ? "this repository grant" : "organization and team membership"}. Other inherited
              access may still apply.
            </DialogDescription>
          </DialogHeader>
          {actionError && (
            <Alert variant="destructive">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button variant="repository" disabled={busy} onClick={() => setRemoving([])}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              loading={busy}
              onClick={() =>
                void perform(async () => {
                  await onRemove(removing)
                  setRemoving([])
                  setSelected(new Set())
                })
              }
            >
              Remove access
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}

type SelectionSetter = Dispatch<SetStateAction<Set<string>>>
const AccessToolbar = ({
  id,
  scope,
  query,
  kind,
  roles,
  canManage,
  busy,
  selectable,
  selected,
  selection,
  allSelected,
  setSelected,
  setRemoving,
  setKind,
  setQuery,
  setPage,
}: {
  id: string
  scope: "repository" | "organization"
  query: string
  kind: string
  roles: AccessRole[]
  canManage: boolean
  busy: boolean
  selectable: AccessEntry[]
  selected: Set<string>
  selection: AccessEntry[]
  allSelected: boolean
  setSelected: SelectionSetter
  setRemoving: (entries: AccessEntry[]) => void
  setKind: (kind: string) => void
  setQuery: (query: string) => void
  setPage: (page: number) => void
}) => (
  <TableHeader appearance="access">
    <TableRow appearance="static">
      <TableHead colSpan={4} appearance="access">
        <div className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="flex items-center gap-3">
            <Checkbox
              appearance="access"
              id={`${id}-all`}
              aria-label="Select all"
              checked={
                allSelected ? true : selectable.some((entry) => selected.has(entry.id)) ? "indeterminate" : false
              }
              disabled={!canManage || busy || !selectable.length}
              onCheckedChange={(checked) =>
                setSelected((current) => {
                  const next = new Set(current)
                  for (const entry of selectable) {
                    if (checked === true) next.add(entry.id)
                    else next.delete(entry.id)
                  }
                  return next
                })
              }
            />
            <Label htmlFor={`${id}-all`} appearance="inline">
              {selection.length ? `${selection.length} selected` : "Select all"}
            </Label>
            {canManage && selection.length > 0 && (
              <Button variant="textDanger" disabled={busy} onClick={() => setRemoving(selection)}>
                Remove selected
              </Button>
            )}
          </div>
          <div className="flex flex-1 items-center justify-end gap-3">
            <FilterDropdown
              label="Type"
              value={kind}
              onChange={(value) => {
                setKind(value)
                setPage(0)
              }}
              defaultValue="all"
              options={
                scope === "repository"
                  ? [
                      { value: "all", label: "All" },
                      { value: "user", label: "Users" },
                      { value: "team", label: "Teams" },
                    ]
                  : [{ value: "all", label: "All roles" }, ...roles]
              }
            />
            <div className="relative min-w-0 max-w-sm flex-1">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground"
              />
              <Input
                appearance="accessSearch"
                aria-label={scope === "repository" ? "Find a collaborator" : "Find a member"}
                placeholder={scope === "repository" ? "Find a collaborator…" : "Find a member…"}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                  setPage(0)
                }}
              />
            </div>
          </div>
        </div>
      </TableHead>
    </TableRow>
  </TableHeader>
)

const AccessTableEntry = ({
  entry,
  roles,
  canManage,
  busy,
  selected,
  setSelected,
  setRemoving,
  perform,
  onRoleChange,
}: {
  entry: AccessEntry
  roles: AccessRole[]
  canManage: boolean
  busy: boolean
  selected: Set<string>
  setSelected: SelectionSetter
  setRemoving: (entries: AccessEntry[]) => void
  perform: (action: () => Promise<void>) => Promise<void>
  onRoleChange: (entry: AccessEntry, role: string) => Promise<void>
}) => (
  <TableRow key={entry.id}>
    <TableCell appearance="selection">
      <Checkbox
        appearance="access"
        aria-label={`Select ${entry.name}`}
        checked={selected.has(entry.id)}
        disabled={!canManage || busy || entry.protected}
        onCheckedChange={(checked) =>
          setSelected((current) => {
            const next = new Set(current)
            if (checked) next.add(entry.id)
            else next.delete(entry.id)
            return next
          })
        }
      />
    </TableCell>
    <TableCell appearance="access">
      <AccessIdentity person={entry} detail={entry.detail} linked />
    </TableCell>
    <TableCell appearance="access">
      <div className="w-28">
        <SelectField
          aria-label={`Role for ${entry.name}`}
          value={entry.role}
          options={
            roles.some((role) => role.value === entry.role)
              ? roles
              : [...roles, { value: entry.role, label: entry.role === "owner" ? "Owner" : entry.role }]
          }
          disabled={!canManage || busy || entry.protected}
          onValueChange={(role) => void perform(() => onRoleChange(entry, role))}
        />
      </div>
    </TableCell>
    <TableCell appearance="action">
      {canManage && (
        <Button
          variant="accessRemove"
          size="icon-lg"
          aria-label={`Remove ${entry.name}`}
          title={entry.protected ? "This role is protected" : `Remove ${entry.name}`}
          disabled={busy || entry.protected}
          onClick={() => setRemoving([entry])}
        >
          <Trash2 className="size-4" aria-hidden="true" />
        </Button>
      )}
    </TableCell>
  </TableRow>
)

const AccessStatus = ({
  loading,
  error,
  scope,
  hasEntries,
  retry,
}: {
  loading: boolean
  error: boolean
  scope: "repository" | "organization"
  hasEntries: boolean
  retry: () => void
}) => {
  const noun = scope === "repository" ? "collaborators" : "members"
  let content = (
    <p role="status">
      {hasEntries
        ? "No matching people."
        : scope === "repository"
          ? "No additional collaborators."
          : "No organization members."}
    </p>
  )
  if (loading) content = <p role="status">Loading {noun}…</p>
  else if (error)
    content = (
      <div className="space-y-2">
        <p role="alert">Unable to load {noun}.</p>
        <Button variant="repository" onClick={retry}>
          Retry
        </Button>
      </div>
    )
  return (
    <TableRow appearance="static">
      <TableCell colSpan={4} appearance="empty">
        {content}
      </TableCell>
    </TableRow>
  )
}
