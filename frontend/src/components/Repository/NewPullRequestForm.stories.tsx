import type { Meta, StoryObj } from "@storybook/react-vite"
import { HttpResponse } from "msw"
import { handleRepositoriesCreatePullRequest } from "@/client/msw.gen"
import { handlers, repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import NewPullRequestForm from "./NewPullRequestForm"
import { trackerPulls } from "./tracker-story-fixtures"

const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/New pull request",
  parameters: {
    msw: {
      handlers: [
        ...handlers,
        handleRepositoriesCreatePullRequest(async ({ request }) =>
          HttpResponse.json({ ...trackerPulls[0], ...(await request.json()) }, { status: 201 }),
        ),
      ],
    },
  },
} satisfies Meta
export default meta
type Story = StoryObj
export const CreatePullRequest: Story = { render: () => <NewPullRequestForm owner="jan-mue" repo="gitedge" /> }
