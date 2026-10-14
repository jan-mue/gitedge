import { createFileRoute } from "@tanstack/react-router"
import { Appearance } from "@/components/Common/Appearance"
import { Page, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/design-system"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import PersonalAccessTokens from "@/components/UserSettings/PersonalAccessTokens"
import UserInformation from "@/components/UserSettings/UserInformation"
import useAuth from "@/hooks/useAuth"

const tabsConfig = [
  { value: "my-profile", title: "My profile", component: UserInformation },
  { value: "password", title: "Password", component: ChangePassword },
  { value: "tokens", title: "Access tokens", component: PersonalAccessTokens },
  { value: "danger-zone", title: "Danger zone", component: DeleteAccount },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
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

      <Tabs defaultValue="my-profile">
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
