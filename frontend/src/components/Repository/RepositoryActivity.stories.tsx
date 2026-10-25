import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import type { RepositoryActivityStatistics } from "@/client"
import { handleActivityGetRepositoryActivityStatistics } from "@/client/msw.gen"
import { repositoryStoryMeta, series } from "@/components/Storybook/repository-fixtures"
import { RepositoryActivity } from "./RepositoryActivity"

const statistics: RepositoryActivityStatistics = {
  start: "2026-10-05T12:00:00Z",
  end: "2026-10-12T12:00:00Z",
  default_branch: "main",
  overview: {
    active_prs: 3,
    active_issues: 2,
    merged_prs: 2,
    proposed_prs: 1,
    closed_issues: 1,
    new_issues: 1,
    merge_authors: 1,
    authors: 2,
    commits: 4,
    branch_commits: 6,
    files_changed: 3,
    additions: 120,
    deletions: 40,
  },
  daily_commits: series,
  merged_prs: [],
  contributors: [{ name: "alice", commits: 4, additions: 120, deletions: 40, series }],
  code_frequency: series,
  recent_commits: series,
}
const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Activity" } satisfies Meta
export default meta
type Story = StoryObj
export const Activity: Story = {
  render: () => <RepositoryActivity owner="jan-mue" repo="gitedge" />,
  parameters: { msw: { handlers: [handleActivityGetRepositoryActivityStatistics({ body: statistics })] } },
}
export const Loading: Story = {
  ...Activity,
  parameters: {
    msw: {
      handlers: [
        handleActivityGetRepositoryActivityStatistics(async () => {
          await delay("infinite")
          return HttpResponse.json(statistics)
        }),
      ],
    },
  },
}
export const ActivityError: Story = {
  ...Activity,
  parameters: {
    msw: {
      handlers: [
        handleActivityGetRepositoryActivityStatistics(() =>
          HttpResponse.json({ detail: "Unavailable" }, { status: 503 }),
        ),
      ],
    },
  },
}
