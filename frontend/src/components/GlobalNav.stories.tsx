import type { Meta, StoryObj } from "@storybook/react-vite"
import { HttpResponse } from "msw"
import {
  handleOrganizationsListOrganizations,
  handleRepositoriesCreateRepository,
  handleUsersReadUserMe,
} from "@/client/msw.gen"
import GlobalNav from "@/components/GlobalNav"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import { storybookSession, storybookUser } from "@/components/Storybook/StoryRouter"

const meta = { ...repositoryStoryMeta, title: "Patterns/Navigation" } satisfies Meta
export default meta
type Story = StoryObj

export const GlobalNavigation: Story = {
  render: () => <GlobalNav />,
  parameters: { msw: { handlers: [handleOrganizationsListOrganizations({ body: { data: [], count: 0 } })] } },
}

export const RepositoryOwner: Story = {
  render: () => <GlobalNav />,
  beforeEach: () => {
    return storybookSession()
  },
  parameters: {
    msw: {
      handlers: [
        handleUsersReadUserMe({
          body: storybookUser,
        }),
        handleOrganizationsListOrganizations({
          body: {
            data: [
              { id: "00000000-0000-0000-0000-000000000003", name: "edge-team", created_at: "2026-10-12T12:00:00Z" },
            ],
            count: 1,
          },
        }),
        handleRepositoriesCreateRepository(async ({ request }) =>
          HttpResponse.json(
            {
              ...(await request.json()),
              default_branch: "main",
              created_at: "2026-10-12T12:00:00Z",
              updated_at: "2026-10-12T12:00:00Z",
            },
            { status: 201 },
          ),
        ),
      ],
    },
  },
}
