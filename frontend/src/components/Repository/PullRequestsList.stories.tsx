import type { Meta, StoryObj } from "@storybook/react-vite"
import { handleRepositoriesListPullRequests } from "@/client/msw.gen"
import PullRequestsList from "@/components/Repository/PullRequestsList"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Pull requests" } satisfies Meta
export default meta
type Story = StoryObj

export const EmptyPullRequests: Story = {
  render: () => <PullRequestsList owner="jan-mue" repo="gitedge" />,
  parameters: {
    msw: {
      handlers: [handleRepositoriesListPullRequests({ body: { data: [], count: 0, open_count: 0, closed_count: 0 } })],
    },
  },
}
