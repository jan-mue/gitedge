import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { z } from "zod"
import { Appearance } from "@/components/Common/Appearance"
import { Page, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/design-system"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import { NotificationPreferences } from "@/components/UserSettings/NotificationPreferences"
import UserInformation from "@/components/UserSettings/UserInformation"
import useAuth from "@/hooks/useAuth"

const tabsConfig = [
  { value: "my-profile", title: "My profile", component: UserInformation },
  { value: "notifications", title: "Notifications", component: NotificationPreferences },
  { value: "password", title: "Password", component: ChangePassword },
  { value: "danger-zone", title: "Danger zone", component: DeleteAccount },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  validateSearch: z.object({
    tab: z.enum(["my-profile", "notifications", "password", "danger-zone"]).optional().catch(undefined),
  }),
  head: () => ({
    meta: [
      {
        title: "Settings - GitEdge",
      },
    ],
  }),
})

function UserSettings() {
  const { user: currentUser } = useAuth()
  const { tab } = Route.useSearch()
  const navigate = useNavigate({ from: "/settings" })
  const finalTabs = tabsConfig

  if (!currentUser) {
    return null
  }

  return (
    <Page>
      <PageHeader
        title="User Settings"
        description="Manage your account settings and preferences"
        actions={<Appearance />}
      />

      <Tabs
        value={tab ?? "my-profile"}
        onValueChange={(value) =>
          navigate({ search: { tab: value as "my-profile" | "notifications" | "password" | "danger-zone" } })
        }
      >
        <TabsList>
          {finalTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.title}
            </TabsTrigger>
          ))}
        </TabsList>
        {finalTabs.map((tab) => (
          <TabsContent key={tab.value} value={tab.value}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </Page>
  )
}
