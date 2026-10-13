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
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
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
      // Mutation errors are displayed by its onError handler.
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
          <div role="alert">
            <p>Unable to load collaborators.</p>
            <Button variant="outline" onClick={() => collaborators.refetch()}>
              Retry
            </Button>
          </div>
        ) : collaborators.data.length ? (
          <ul className="divide-y">
            {collaborators.data.map((collaborator) => (
              <li key={collaborator.id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="min-w-0 flex-1 break-words">
                  {collaborator.subject_name}
                  <span className="ml-2 text-xs text-muted-foreground">{collaborator.team_id ? "Team" : "User"}</span>
                </span>
                <select
                  aria-label={`Role for ${collaborator.subject_name}`}
                  value={collaborator.role}
                  disabled={busy || (collaborator.role === "owner" && !canManageOwners)}
                  onChange={(event) =>
                    grant.mutate({
                      path,
                      body: {
                        user_id: collaborator.user_id,
                        team_id: collaborator.team_id,
                        role: event.target.value as RepositoryRole,
                      },
                    })
                  }
                  className="rounded border bg-background px-3 py-2 text-sm"
                >
                  {(collaborator.role === "owner" && !canManageOwners ? ["owner" as const] : roles).map((item) => (
                    <option key={item} value={item}>
                      {roleLabels[item]}
                    </option>
                  ))}
                </select>
                <Button
                  variant="outline"
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
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault()
            void add()
          }}
        >
          <div>
            <label htmlFor="collaborator-kind" className="mb-1 block text-sm font-medium">
              Collaborator type
            </label>
            <select
              id="collaborator-kind"
              value={kind}
              onChange={(event) => setKind(event.target.value as "user" | "team")}
              className="w-full rounded border bg-background px-3 py-2 text-sm"
            >
              <option value="user">User</option>
              {!!teams.data?.length && <option value="team">Organization team</option>}
            </select>
          </div>
          <div>
            <label htmlFor="collaborator-subject" className="mb-1 block text-sm font-medium">
              {kind === "user" ? "Username" : "Team"}
            </label>
            {kind === "user" ? (
              <Input
                id="collaborator-subject"
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            ) : (
              <select
                id="collaborator-subject"
                required
                value={teamId}
                onChange={(event) => setTeamId(event.target.value)}
                className="w-full rounded border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select a team</option>
                {teams.data?.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div>
            <label htmlFor="collaborator-role" className="mb-1 block text-sm font-medium">
              Role
            </label>
            <select
              id="collaborator-role"
              value={role}
              onChange={(event) => setRole(event.target.value as RepositoryRole)}
              className="w-full rounded border bg-background px-3 py-2 text-sm"
            >
              {roles.map((item) => (
                <option key={item} value={item}>
                  {roleLabels[item]}
                </option>
              ))}
            </select>
          </div>
          <LoadingButton className="self-end" type="submit" loading={busy}>
            Add collaborator
          </LoadingButton>
        </form>
      </div>
    </section>
  )
}

export default RepositoryCollaborators
