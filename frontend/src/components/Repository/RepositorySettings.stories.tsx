import type { Meta, StoryObj } from "@storybook/react-vite"
import { HttpResponse } from "msw"
import type { Repository } from "@/client"
import {
  handleAuthorizationGetPermissions,
  handleRepositoriesDeleteRepository,
  handleRepositoriesGetRepository,
  handleRepositoriesUpdateRepository,
  handleUsersReadUserMe,
} from "@/client/msw.gen"
import { createCollaboratorFixtures } from "@/components/Storybook/authorization-fixtures"
import { handlers, repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import RepositorySettings from "./RepositorySettings"

const initialRepository: Repository = {
  name: "gitedge",
  owner: "jan-mue",
  description: "Git hosting at the edge",
  default_branch: "main",
  is_private: false,
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-12T12:00:00Z",
}
let repository = initialRepository
const collaborators = createCollaboratorFixtures()
const ownerPermissions = handleAuthorizationGetPermissions({
  body: { read: true, write: true, admin: true, owner: true },
})

const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/Settings",
  beforeEach: () => {
    repository = initialRepository
    collaborators.reset()
    const previous = localStorage.getItem("access_token")
    localStorage.setItem("access_token", "storybook-session")
    return () => {
      if (previous === null) localStorage.removeItem("access_token")
      else localStorage.setItem("access_token", previous)
    }
  },
  parameters: {
    msw: {
      handlers: [
        ...handlers,
        ...collaborators.handlers,
        ownerPermissions,
        handleUsersReadUserMe({
          body: {
            id: "00000000-0000-0000-0000-000000000001",
            name: "jan-mue",
            email: "jan@example.com",
            is_active: true,
          },
        }),
        handleRepositoriesGetRepository(() => HttpResponse.json(repository)),
        handleRepositoriesUpdateRepository(async ({ request }) => {
          const update = await request.json()
          repository = {
            ...repository,
            ...update,
            name: update.name ?? repository.name,
            default_branch: update.default_branch ?? repository.default_branch,
            is_private: update.is_private ?? repository.is_private,
          }
          return HttpResponse.json(repository)
        }),
        handleRepositoriesDeleteRepository(() => new HttpResponse(null, { status: 204 })),
      ],
    },
  },
} satisfies Meta
export default meta
type Story = StoryObj
export const Settings: Story = { render: () => <RepositorySettings owner="jan-mue" repo="gitedge" /> }

export const Admin: Story = {
  ...Settings,
  parameters: {
    msw: {
      handlers: [
        handleAuthorizationGetPermissions({ body: { read: true, write: true, admin: true, owner: false } }),
        ...meta.parameters.msw.handlers.filter((handler) => handler !== ownerPermissions),
      ],
    },
  },
}
