import type { Meta, StoryObj } from "@storybook/react-vite"
import { HttpResponse } from "msw"
import { handleRepositoriesListIssues } from "@/client/msw.gen"
import IssuesList from "@/components/Repository/IssuesList"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Issues" } satisfies Meta
export default meta
type Story = StoryObj

export const EmptyIssues: Story = {
  render: () => <IssuesList owner="jan-mue" repo="gitedge" />,
  parameters: {
    msw: { handlers: [handleRepositoriesListIssues({ body: { data: [], count: 0, open_count: 0, closed_count: 0 } })] },
  },
}
export const IssuesError: Story = {
  ...EmptyIssues,
  parameters: {
    msw: {
      handlers: [handleRepositoriesListIssues(() => HttpResponse.json({ detail: "Unavailable" }, { status: 503 }))],
    },
  },
}
