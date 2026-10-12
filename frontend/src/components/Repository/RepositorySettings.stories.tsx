import type { Meta, StoryObj } from "@storybook/react-vite"
import { handleRepositoriesGetRepository, handleUsersReadUserMe } from "@/client/msw.gen"
import { handlers, repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import RepositorySettings from "./RepositorySettings"

const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/Settings",
  beforeEach: () => {
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
        handleUsersReadUserMe({
          body: {
            id: "00000000-0000-0000-0000-000000000001",
            name: "jan-mue",
            email: "jan@example.com",
            is_active: true,
          },
        }),
        handleRepositoriesGetRepository({
          body: {
            name: "gitedge",
            owner: "jan-mue",
            description: "Git hosting at the edge",
            default_branch: "main",
            is_private: false,
            created_at: "2026-10-01T12:00:00Z",
            updated_at: "2026-10-12T12:00:00Z",
          },
        }),
      ],
    },
  },
} satisfies Meta
export default meta
type Story = StoryObj
export const Settings: Story = { render: () => <RepositorySettings owner="jan-mue" repo="gitedge" /> }
