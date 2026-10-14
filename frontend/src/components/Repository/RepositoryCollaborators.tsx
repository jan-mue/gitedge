import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import type { CollaboratorInput, RepositoryRole } from "@/client"
import { ProfilesService } from "@/client"
import {
  authorizationListCollaboratorsOptions,
  authorizationListCollaboratorTeamsOptions,
  authorizationRemoveCollaboratorMutation,
  authorizationSetCollaboratorMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Input,
  Label,
  LoadingButton,
  SelectField,
} from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const roleLabels: Record<RepositoryRole, string> = {
  read: "Read",
  write: "Write",
  admin: "Admin",
  owner: "Owner",
}

const RepositoryCollaborators = ({
  owner,
  repo,
  canManageOwners,
}: {
  owner: string
  repo: string
  canManageOwners: boolean
}) => {
  const path = { owner, repo }
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [kind, setKind] = useState<"user" | "team">("user")
  const [username, setUsername] = useState("")
  const [teamId, setTeamId] = useState("")
  const [role, setRole] = useState<RepositoryRole>("read")
  const [resolving, setResolving] = useState(false)
  const collaborators = useQuery(authorizationListCollaboratorsOptions({ path }))
  const teams = useQuery(authorizationListCollaboratorTeamsOptions({ path }))
  const refresh = async () => {
    await queryClient.invalidateQueries()
    showSuccessToast("Collaborators updated")
  }
  const grant = useMutation({
    ...authorizationSetCollaboratorMutation(),
    onSuccess: refresh,
    onError: handleError.bind(showErrorToast),
  })
  const remove = useMutation({
    ...authorizationRemoveCollaboratorMutation(),
    onSuccess: refresh,
    onError: handleError.bind(showErrorToast),
  })
  const busy = grant.isPending || remove.isPending || resolving
  const roles = (Object.keys(roleLabels) as RepositoryRole[]).filter((item) => item !== "owner" || canManageOwners)
  const add = async () => {
    setResolving(true)
    let mutationStarted = false
    try {
      let body: CollaboratorInput
      if (kind === "team") {
        body = { team_id: teamId, role }
      } else {
        const { data: user } = await ProfilesService.readUserByUsername({
          path: { username: username.trim() },
          throwOnError: true,
        })
        if (user.principal_type !== "user") throw new Error("Choose an individual user or select an organization team.")
        body = { user_id: user.id, role }
      }
      mutationStarted = true
      await grant.mutateAsync({ path, body })
      setUsername("")
    } catch (error) {
      if (!mutationStarted) handleError.call(showErrorToast, error)
    } finally {
      setResolving(false)
    }
  }
  return (
    <section id="collaborators" className="overflow-hidden rounded border bg-card">
      <h3 className="border-b bg-secondary px-4 py-3 text-xl font-semibold">Collaborators</h3>
      <div className="space-y-4 p-4">
        <p className="text-sm text-muted-foreground">
          Grant access to users or organization teams. Organization admins and the repository's account owner have owner
          access.
        </p>
        <p className="text-sm text-muted-foreground">
          Read allows browsing and cloning. Write adds push and release access. Admin adds settings and collaborator
          management. Owner adds deletion and owner-role management.
        </p>
        {collaborators.isPending ? (
          <p role="status">Loading collaborators…</p>
        ) : collaborators.isError ? (
          <Alert variant="destructive">
            <AlertDescription>Unable to load collaborators.</AlertDescription>
            <div className="mt-3">
              <Button variant="repository" onClick={() => collaborators.refetch()}>
                Retry
              </Button>
            </div>
          </Alert>
        ) : collaborators.data.length ? (
          <ul className="divide-y divide-border">
            {collaborators.data.map((collaborator) => (
              <li key={collaborator.id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="min-w-0 flex-1 break-words">{collaborator.subject_name}</span>
                <Badge variant="secondary">{collaborator.team_id ? "Team" : "User"}</Badge>
                <div className="w-32">
                  <SelectField
                    aria-label={`Role for ${collaborator.subject_name}`}
                    value={collaborator.role}
                    disabled={busy || (collaborator.role === "owner" && !canManageOwners)}
                    onValueChange={(value) =>
                      grant.mutate({
                        path,
                        body: {
                          user_id: collaborator.user_id,
                          team_id: collaborator.team_id,
                          role: value as RepositoryRole,
                        },
                      })
                    }
                    options={(collaborator.role === "owner" && !canManageOwners ? ["owner" as const] : roles).map(
                      (item) => ({ value: item, label: roleLabels[item] }),
                    )}
                  />
                </div>
                <Button
                  variant="dangerOutline"
                  size="compact"
                  disabled={busy || (collaborator.role === "owner" && !canManageOwners)}
                  onClick={() => remove.mutate({ path: { ...path, collaborator_id: collaborator.id } })}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No additional collaborators.</p>
        )}
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault()
            void add()
          }}
        >
          <div>
            <Label htmlFor="collaborator-kind" appearance="field">
              Collaborator type
            </Label>
            <SelectField
              id="collaborator-kind"
              value={kind}
              disabled={busy}
              onValueChange={(value) => {
                setKind(value as "user" | "team")
                setTeamId("")
              }}
              options={[
                { value: "user", label: "User" },
                ...(teams.data?.length ? [{ value: "team", label: "Organization team" }] : []),
              ]}
            />
          </div>
          <div>
            <Label htmlFor="collaborator-subject" appearance="field">
              {kind === "user" ? "Username" : "Team"}
            </Label>
            {kind === "user" ? (
              <Input
                id="collaborator-subject"
                required
                disabled={busy}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            ) : (
              <SelectField
                id="collaborator-subject"
                required
                disabled={busy}
                value={teamId}
                onValueChange={setTeamId}
                placeholder="Select a team"
                options={(teams.data ?? []).map((team) => ({ value: team.id, label: team.name }))}
              />
            )}
          </div>
          <div>
            <Label htmlFor="collaborator-role" appearance="field">
              Role
            </Label>
            <SelectField
              id="collaborator-role"
              value={role}
              disabled={busy}
              onValueChange={(value) => setRole(value as RepositoryRole)}
              options={roles.map((item) => ({ value: item, label: roleLabels[item] }))}
            />
          </div>
          <div className="self-end">
            <LoadingButton variant="success" type="submit" loading={busy} disabled={kind === "team" && !teamId}>
              Add collaborator
            </LoadingButton>
          </div>
        </form>
      </div>
    </section>
  )
}

export default RepositoryCollaborators
