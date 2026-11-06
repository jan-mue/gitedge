import { useQuery, useQueryClient } from "@tanstack/react-query"
import { AuthorizationService } from "@/client"
import {
  authorizationGetOrganizationPermissionsOptions,
  authorizationListMembersOptions,
} from "@/client/@tanstack/react-query.gen"
import { AccessTable } from "@/components/Access/AccessTable"

const organizationRoles = [
  { value: "member", label: "Member" },
  { value: "admin", label: "Admin" },
]

export const OrganizationMembers = ({ organization }: { organization: string }) => {
  const path = { organization }
  const queryClient = useQueryClient()
  const options = authorizationListMembersOptions({ path })
  const members = useQuery(authorizationListMembersOptions({ path }))
  const permissions = useQuery(authorizationGetOrganizationPermissionsOptions({ path }))
  const adminCount = members.data?.filter((member) => member.is_admin).length ?? 0
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: options.queryKey }),
      queryClient.invalidateQueries({ queryKey: authorizationGetOrganizationPermissionsOptions({ path }).queryKey }),
    ])
  }
  const grant = (id: string, role: string) =>
    AuthorizationService.setMember({
      path: { ...path, user_id: id },
      body: { is_admin: role === "admin" },
      throwOnError: true,
    })
  return (
    <AccessTable
      target={organization}
      scope="organization"
      roles={organizationRoles}
      canManage={permissions.data?.admin === true}
      entries={(members.data ?? []).map((member) => ({
        id: member.user_id,
        name: member.name,
        displayName: member.display_name,
        kind: "user",
        role: member.is_admin ? "admin" : "member",
        detail: "Organization member",
        protected: member.is_admin && adminCount === 1,
      }))}
      loading={members.isPending || permissions.isPending}
      error={members.isError || permissions.isError}
      retry={() => {
        void members.refetch()
        void permissions.refetch()
      }}
      onAdd={async (people, role) => {
        try {
          for (const person of people) await grant(person.id, role)
        } finally {
          await refresh()
        }
      }}
      onRoleChange={async (entry, role) => {
        try {
          await grant(entry.id, role)
        } finally {
          await refresh()
        }
      }}
      onRemove={async (selected) => {
        try {
          for (const entry of selected)
            await AuthorizationService.removeMember({ path: { ...path, user_id: entry.id }, throwOnError: true })
        } finally {
          await refresh()
        }
      }}
    />
  )
}
