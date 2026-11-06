import { useQuery } from "@tanstack/react-query"
import { Search } from "lucide-react"
import { useEffect, useId, useState } from "react"
import {
  authorizationSearchCollaboratorCandidatesOptions,
  authorizationSearchMemberCandidatesOptions,
} from "@/client/@tanstack/react-query.gen"
import {
  Alert,
  AlertDescription,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  SelectField,
} from "@/components/design-system"
import { AccessIdentity, type AccessPerson } from "./AccessIdentity"

export interface AccessRole {
  value: string
  label: string
}

export const AddPeopleDialog = ({
  open,
  onOpenChange,
  target,
  scope,
  existing,
  roles,
  teams = [],
  repositoryOwner = "",
  onAdd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  target: string
  scope: "repository" | "organization"
  existing: Set<string>
  roles: AccessRole[]
  teams?: AccessPerson[]
  repositoryOwner?: string
  onAdd: (people: AccessPerson[], role: string) => Promise<void>
}) => {
  const id = useId()
  const [query, setQuery] = useState("")
  const [debounced, setDebounced] = useState("")
  const [selected, setSelected] = useState<AccessPerson[]>([])
  const [role, setRole] = useState(roles[0]?.value ?? "")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(timer)
  }, [query])
  const repositoryCandidates = useQuery({
    ...authorizationSearchCollaboratorCandidatesOptions({
      path: { owner: repositoryOwner, repo: target },
      query: { q: debounced },
    }),
    enabled: open && scope === "repository" && debounced.length > 0,
  })
  const organizationCandidates = useQuery({
    ...authorizationSearchMemberCandidatesOptions({ path: { organization: target }, query: { q: debounced } }),
    enabled: open && scope === "organization" && debounced.length > 0,
  })
  const candidates = scope === "repository" ? repositoryCandidates : organizationCandidates
  const people = [
    ...(debounced === query.trim()
      ? (candidates.data ?? []).map((user) => ({
          id: user.id,
          name: user.name,
          displayName: user.display_name,
          kind: "user" as const,
        }))
      : []),
    ...teams.filter((team) => team.name.toLowerCase().includes(query.trim().toLowerCase())),
  ].filter((person) => !existing.has(person.id))
  const submit = async () => {
    setBusy(true)
    setError("")
    try {
      await onAdd(selected, role)
      onOpenChange(false)
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to add people. Please try again.")
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) onOpenChange(value)
      }}
    >
      <DialogContent appearance="access">
        <DialogHeader>
          <DialogTitle>Add people to {target}</DialogTitle>
          <div className="sr-only">
            <DialogDescription>
              Choose people{teams.length ? " or organization teams" : ""} and the role to grant.
            </DialogDescription>
          </div>
        </DialogHeader>
        <div className="space-y-3">
          <Label htmlFor={`${id}-search`} appearance="access">
            Search by username, full name, or email
          </Label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground"
            />
            <Input
              id={`${id}-search`}
              appearance="accessSearch"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
              disabled={busy}
            />
          </div>
        </div>
        <section
          className="h-72 overflow-y-auto rounded-md border border-border"
          aria-label="People to add"
          aria-busy={candidates.isFetching}
        >
          {people.map((person) => (
            <Button
              key={person.id}
              variant="accessCandidate"
              aria-pressed={selected.some((item) => item.id === person.id)}
              disabled={busy}
              onClick={() =>
                setSelected((current) =>
                  current.some((item) => item.id === person.id)
                    ? current.filter((item) => item.id !== person.id)
                    : [...current, person],
                )
              }
            >
              <AccessIdentity
                person={person}
                detail={
                  person.kind === "team"
                    ? "Add team"
                    : scope === "repository"
                      ? "Invite collaborator"
                      : "Add organization member"
                }
              />
            </Button>
          ))}
          {candidates.isError ? (
            <div className="p-5">
              <Alert variant="destructive">
                <AlertDescription>Unable to search people.</AlertDescription>
                <Button variant="text" onClick={() => candidates.refetch()}>
                  Retry
                </Button>
              </Alert>
            </div>
          ) : (
            !people.length && (
              <p role="status" className="p-5 text-sm text-muted-foreground">
                {candidates.isFetching || debounced !== query.trim()
                  ? "Searching…"
                  : query.trim()
                    ? "No people found."
                    : "Search for people to add."}
              </p>
            )
          )}
        </section>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <DialogFooter>
          <div className="mr-auto flex flex-wrap items-center gap-4">
            <span className="text-sm text-muted-foreground" role="status">
              {selected.length} selected
            </span>
            <div className="flex items-center gap-3">
              <Label htmlFor={`${id}-role`}>Role</Label>
              <div className="w-28">
                <SelectField id={`${id}-role`} value={role} onValueChange={setRole} options={roles} disabled={busy} />
              </div>
            </div>
          </div>

          <Button variant="repository" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="success"
            disabled={!selected.length || !roles.some((item) => item.value === role)}
            loading={busy}
            onClick={submit}
          >
            Add to {scope}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
