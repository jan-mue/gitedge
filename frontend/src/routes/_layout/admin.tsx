import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"
import { type UserPublic, UsersService } from "@/client"
import { usersReadUsersOptions } from "@/client/@tanstack/react-query.gen"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { OrganizationsPanel } from "@/components/Admin/OrganizationsPanel"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Page, PageHeader, SectionHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/design-system"
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

function Admin() {
  return (
    <Page>
      <PageHeader title="Site Administration" description="Manage users, organizations and permissions" />

      <Tabs defaultValue="users" appearance="spaced">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="organizations">Organizations</TabsTrigger>
        </TabsList>

        <TabsContent value="users" appearance="spaced">
          <SectionHeader title="Users" description="Manage user accounts and permissions" actions={<AddUser />} />
          <UsersTable />
        </TabsContent>

        <TabsContent value="organizations">
          <OrganizationsPanel />
        </TabsContent>
      </Tabs>
    </Page>
  )
}
