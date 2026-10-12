import type { Meta } from "@storybook/react-vite"
import {
  handleForksListForks,
  handleReleasesListTags,
  handleRepositoriesGetRepositoryInfo,
  handleRepositoriesGetStatistics,
  handleRepositoriesListBranches,
  handleStarsGetStarState,
  handleStarsStarRepository,
  handleStarsUnstarRepository,
  handleWatchersGetWatchState,
  handleWatchersUnwatchRepository,
  handleWatchersWatchRepository,
} from "@/client/msw.gen"
import { StoryRouter } from "@/components/Storybook/StoryRouter"
export const handlers = [
  handleReleasesListTags({
    body: {
      data: [
        { name: "v1.0.0", commit_sha: "abcdef1234567890" },
        { name: "v0.9.0", commit_sha: "1234567890abcdef" },
      ],
      count: 2,
    },
  }),
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
  handleStarsStarRepository({ body: { is_starred: true, stars_count: 129 } }),
  handleStarsUnstarRepository({ body: { is_starred: false, stars_count: 128 } }),
  handleWatchersWatchRepository({ body: { is_watching: true, watchers_count: 33 } }),
  handleWatchersUnwatchRepository({ body: { is_watching: false, watchers_count: 32 } }),
]
export const repositoryStoryMeta = {
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
export const series = Array.from({ length: 12 }, (_, i) => ({
  date: `2026-09-${String(i + 1).padStart(2, "0")}`,
  commits: (i * 7) % 23,
  additions: 50 + i * 15,
  deletions: 10 + i * 5,
}))
