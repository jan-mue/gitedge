import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import {
  handleForksListForks,
  handleOrganizationsListOrganizations,
  handleRepositoriesGetRepositoryInfo,
  handleRepositoriesGetStatistics,
  handleRepositoriesListBranches,
  handleRepositoriesListIssues,
  handleRepositoriesListPullRequests,
  handleStarsGetStarState,
  handleWatchersGetWatchState,
} from "@/client/msw.gen"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"
import FeedLoading from "@/components/Dashboard/FeedLoading"
import GlobalNav from "@/components/GlobalNav"
import ActivityChart from "@/components/Repository/ActivityChart"
import ActivityLoading from "@/components/Repository/ActivityLoading"
import FileBrowser from "@/components/Repository/FileBrowser"
import IssuesList from "@/components/Repository/IssuesList"
import PullRequestsList from "@/components/Repository/PullRequestsList"
import ReadmeViewer from "@/components/Repository/ReadmeViewer"
import RepoHeader from "@/components/Repository/RepoHeader"
import RepoStats from "@/components/Repository/RepoStats"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import SourceLoading from "@/components/Repository/SourceLoading"
import { StoryRouter } from "./story-router"

const handlers = [
  handleStarsGetStarState({ body: { is_starred: false, stars_count: 128 } }),
  handleWatchersGetWatchState({ body: { is_watching: false, watchers_count: 32 } }),
  handleForksListForks({ body: { data: [], count: 24 } }),
  handleRepositoriesGetRepositoryInfo({
    body: {
      owner: "jan-mue",
      name: "gitedge",
      description: "Git hosting at the edge",
      default_branch: "main",
      branch_count: 3,
      tag_count: 8,
    },
  }),
  handleRepositoriesGetStatistics({
    body: {
      commit_count: 255,
      size: 142000,
      languages: [
        { name: "Python", percentage: 65, size: 92300 },
        { name: "TypeScript", percentage: 35, size: 49700 },
      ],
    },
  }),
  handleRepositoriesListBranches({
    body: [
      { name: "main", is_default: true },
      { name: "develop", is_default: false },
    ],
  }),
]
const meta = {
  title: "Patterns/Repository",
  decorators: [
    (Story) => (
      <StoryRouter>
        <Story />
      </StoryRouter>
    ),
  ],
  parameters: { msw: { handlers } },
} satisfies Meta
export default meta
type Story = StoryObj
export const Header: Story = { render: () => <RepoHeader owner="jan-mue" repo="gitedge" /> }
export const SelectedActions: Story = {
  ...Header,
  parameters: {
    msw: {
      handlers: [
        handleStarsGetStarState({ body: { is_starred: true, stars_count: 129 } }),
        handleWatchersGetWatchState({ body: { is_watching: true, watchers_count: 33 } }),
        ...handlers.slice(2),
      ],
    },
  },
}
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
        ...handlers.filter((_, i) => i !== 4),
      ],
    },
  },
}
export const FileTree: Story = {
  render: () => (
    <FileBrowser
      owner="jan-mue"
      repo="gitedge"
      entries={[
        { name: "frontend", path: "frontend", type: "tree" },
        { name: "backend", path: "backend", type: "tree" },
        { name: "README.md", path: "README.md", type: "blob", size: 4096 },
        { name: "bun.lock", path: "bun.lock", type: "blob", size: 62000 },
      ]}
      lastCommit={{
        sha: "ce65263abc123456",
        author: "Jan",
        message: "Build the GitEdge design system",
        timestamp: 1791756000,
      }}
    />
  ),
}
export const NestedTree: Story = {
  render: () => (
    <FileBrowser
      owner="jan-mue"
      repo="gitedge"
      treePath="frontend/src"
      entries={[
        { name: "components", path: "frontend/src/components", type: "tree" },
        { name: "main.tsx", path: "frontend/src/main.tsx", type: "blob", size: 2048 },
      ]}
    />
  ),
}
export const EmptyTree: Story = { render: () => <FileBrowser owner="jan-mue" repo="gitedge" entries={[]} /> }
export const RepositorySkeleton: Story = { render: () => <RepositoryLoading /> }
export const FileSkeleton: Story = { render: () => <SourceLoading kind="blob" /> }
export const DirectorySkeleton: Story = { render: () => <SourceLoading kind="tree" /> }
export const PathSkeleton: Story = { render: () => <SourceLoading /> }
export const ActivitySkeleton: Story = { render: () => <ActivityLoading view="pulse" /> }
export const FeedSkeleton: Story = { render: () => <FeedLoading /> }
export const RetryError: Story = {
  render: () => <RepositoryError message="Unable to load this repository." retry={() => {}} />,
}
export const Readme: Story = {
  render: () => (
    <ReadmeViewer
      content=""
      html={
        "<h1>GitEdge</h1><p>Git hosting at the <strong>edge</strong>. Built for developers.</p><h2>Getting started</h2><pre><code>git clone https://gitedge-app.vercel.app/jan-mue/gitedge.git</code></pre><ul><li>Blob-backed Git objects</li><li>Fast repository browsing</li></ul><blockquote>Push your code. Keep moving.</blockquote><table><thead><tr><th>Feature</th><th>Status</th></tr></thead><tbody><tr><td>Repository browsing</td><td>Available</td></tr></tbody></table>"
      }
    />
  ),
}
export const ReadmeFallback: Story = {
  render: () => <ReadmeViewer content="# GitEdge\n\nGit hosting at the edge." html="" />,
}
const series = Array.from({ length: 12 }, (_, i) => ({
  date: `2026-09-${String(i + 1).padStart(2, "0")}`,
  commits: (i * 7) % 23,
  additions: 50 + i * 15,
  deletions: 10 + i * 5,
}))
export const BarChart: Story = { render: () => <ActivityChart series={series} label="Weekly commits" /> }
export const AreaChart: Story = {
  render: () => <ActivityChart series={series} variant="area" label="Commit history" interactive />,
}
export const FrequencyChart: Story = {
  render: () => <ActivityChart series={series} variant="frequency" label="Code additions and deletions" />,
}
export const EmptyChart: Story = { render: () => <ActivityChart series={[]} label="No commits yet" /> }
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
export const EmptyPullRequests: Story = {
  render: () => <PullRequestsList owner="jan-mue" repo="gitedge" />,
  parameters: {
    msw: {
      handlers: [handleRepositoriesListPullRequests({ body: { data: [], count: 0, open_count: 0, closed_count: 0 } })],
    },
  },
}
export const ContributorSkeleton: Story = { render: () => <ActivityLoading view="contributors" /> }
export const FrequencySkeleton: Story = { render: () => <ActivityLoading view="code-frequency" /> }
export const CommitsSkeleton: Story = { render: () => <ActivityLoading view="recent-commits" /> }

export const NotFoundPage: Story = { render: () => <NotFound /> }
export const ErrorPage: Story = { render: () => <ErrorComponent /> }

export const GlobalNavigation: Story = {
  render: () => <GlobalNav />,
  parameters: { msw: { handlers: [handleOrganizationsListOrganizations({ body: { data: [], count: 0 } })] } },
}
