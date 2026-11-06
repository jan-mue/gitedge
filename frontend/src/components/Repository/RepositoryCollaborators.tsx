import { useQuery, useQueryClient } from "@tanstack/react-query"
import { AuthorizationService, type RepositoryRole } from "@/client"
import {
  authorizationListCollaboratorsOptions,
  authorizationListCollaboratorTeamsOptions,
} from "@/client/@tanstack/react-query.gen"
import { type AccessEntry, AccessTable } from "@/components/Access/AccessTable"

const repositoryRoles = [
  { value: "read", label: "Read" },
  { value: "write", label: "Write" },
  { value: "admin", label: "Admin" },
  { value: "owner", label: "Owner" },
]

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
  const options = authorizationListCollaboratorsOptions({ path })
  const collaborators = useQuery(authorizationListCollaboratorsOptions({ path }))
  const teams = useQuery(authorizationListCollaboratorTeamsOptions({ path }))
  const roles = repositoryRoles.filter((role) => role.value !== "owner" || canManageOwners)
  const refresh = () => queryClient.invalidateQueries({ queryKey: options.queryKey })
  const entries: AccessEntry[] = (collaborators.data ?? []).map((collaborator) => ({
    id: (collaborator.user_id ?? collaborator.team_id) as string,
    name: collaborator.subject_name,
    displayName: collaborator.display_name,
    kind: collaborator.team_id ? "team" : "user",
    role: collaborator.role,
    protected: collaborator.role === "owner" && !canManageOwners,
    detail: collaborator.team_id ? "Organization team" : "Collaborator",
  }))
  const grant = async (id: string, kind: "user" | "team", role: string) => {
    await AuthorizationService.setCollaborator({
      path,
      body: { ...(kind === "team" ? { team_id: id } : { user_id: id }), role: role as RepositoryRole },
      throwOnError: true,
    })
  }
  return (
    <AccessTable
      target={repo}
      scope="repository"
      entries={entries}
      roles={roles}
      loading={collaborators.isPending}
      error={collaborators.isError}
      retry={() => {
        void collaborators.refetch()
      }}
      teams={(teams.data ?? []).map((team) => ({ id: team.id, name: team.name, kind: "team" }))}
      repositoryOwner={owner}
      onAdd={async (people, role) => {
        try {
          for (const person of people) await grant(person.id, person.kind, role)
        } finally {
          await refresh()
        }
      }}
      onRoleChange={async (entry, role) => {
        try {
          await grant(entry.id, entry.kind, role)
        } finally {
          await refresh()
        }
      }}
      onRemove={async (selected) => {
        try {
          for (const entry of selected) {
            const collaborator = collaborators.data?.find((item) => (item.user_id ?? item.team_id) === entry.id)
            if (collaborator)
              await AuthorizationService.removeCollaborator({
                path: { ...path, collaborator_id: collaborator.id },
                throwOnError: true,
              })
          }
        } finally {
          await refresh()
        }
      }}
    />
  )
}

export default RepositoryCollaborators
