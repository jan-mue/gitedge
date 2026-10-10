import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Building2 } from "lucide-react"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import { organizationsListOrganizationsOptions, usersReadUsersOptions } from "@/client/@tanstack/react-query.gen"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Admin - GitEdge",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(usersReadUsersOptions({ query: { skip: 0, limit: 100 } }))

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function OrganizationsContent() {
  const { data: organizations } = useSuspenseQuery(
    organizationsListOrganizationsOptions({ query: { offset: 0, limit: 100 } }),
  )

  if (organizations.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
        <Building2 className="mb-3 h-10 w-10 text-muted-foreground opacity-60" />
        <h3 className="text-lg font-semibold text-foreground">No organizations yet</h3>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">
          Organizations let you group repositories and manage team access.
        </p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      {organizations.data.map((organization, index) => (
        <div
          key={organization.id}
          className={`flex items-center gap-3 px-4 py-3 ${
            index < organizations.data.length - 1 ? "border-b border-border" : ""
          }`}
          data-testid={`organization-${organization.name}`}
        >
          <Building2 className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-foreground">{organization.name}</span>
          {organization.description && (
            <span className="truncate text-sm text-muted-foreground">{organization.description}</span>
          )}
        </div>
      ))}
    </div>
  )
}

function OrganizationsPanel() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <OrganizationsContent />
    </Suspense>
  )
}

function Admin() {
  return (
    <div className="container mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Site Administration</h1>
        <p className="text-muted-foreground">Manage users, organizations and permissions</p>
      </div>

      <Tabs defaultValue="users" className="space-y-4">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="organizations">Organizations</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Users</h2>
              <p className="text-muted-foreground">Manage user accounts and permissions</p>
            </div>
            <AddUser />
          </div>
          <UsersTable />
        </TabsContent>

        <TabsContent value="organizations">
          <OrganizationsPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
