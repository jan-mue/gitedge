import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import { handleAuthorizationListCollaborators } from "@/client/msw.gen"
import { createCollaboratorFixtures } from "@/components/Storybook/authorization-fixtures"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import RepositoryCollaborators from "./RepositoryCollaborators"

const fixtures = createCollaboratorFixtures()
const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/Collaborators",
  component: RepositoryCollaborators,
  args: { owner: "jan-mue", repo: "gitedge", canManageOwners: true },
  beforeEach: fixtures.reset,
  parameters: { msw: { handlers: fixtures.handlers } },
} satisfies Meta<typeof RepositoryCollaborators>
export default meta
type Story = StoryObj<typeof meta>
export const Owner: Story = {}
export const Admin: Story = { args: { canManageOwners: false } }
export const Empty: Story = {
  parameters: { msw: { handlers: [handleAuthorizationListCollaborators({ body: [] }), ...fixtures.handlers] } },
}
export const Loading: Story = {
  parameters: {
    msw: {
      handlers: [
        handleAuthorizationListCollaborators(async () => {
          await delay("infinite")
          return HttpResponse.json([])
        }),
        ...fixtures.handlers,
      ],
    },
  },
}
export const Unavailable: Story = {
  parameters: {
    msw: {
      handlers: [
        handleAuthorizationListCollaborators(() => HttpResponse.json({ detail: "Unavailable" }, { status: 503 })),
        ...fixtures.handlers,
      ],
    },
  },
}
