import type { Meta, StoryObj } from "@storybook/react-vite"
import { handleOrganizationsListOrganizations } from "@/client/msw.gen"
import GlobalNav from "@/components/GlobalNav"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Navigation" } satisfies Meta
export default meta
type Story = StoryObj

export const GlobalNavigation: Story = {
  render: () => <GlobalNav />,
  parameters: { msw: { handlers: [handleOrganizationsListOrganizations({ body: { data: [], count: 0 } })] } },
}
