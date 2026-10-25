import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import { handleRepositoriesGetStatistics } from "@/client/msw.gen"
import RepoStats from "@/components/Repository/RepoStats"
import { handlers, repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Statistics" } satisfies Meta
export default meta
type Story = StoryObj

export const Statistics: Story = { render: () => <RepoStats owner="jan-mue" repo="gitedge" gitRef="main" /> }
export const StatisticsLoading: Story = {
  ...Statistics,
  parameters: {
    msw: {
      handlers: [
        handleRepositoriesGetStatistics(async () => {
          await delay("infinite")
          return HttpResponse.json({})
        }),
        ...handlers,
      ],
    },
  },
}
