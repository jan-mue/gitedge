import type { Meta, StoryObj } from "@storybook/react-vite"
import { HttpResponse } from "msw"
import type { ReviewPublic } from "@/client"
import {
  handleCommentsListComments,
  handleRepositoriesGetPullRequest,
  handleRepositoriesGetPullRequestCommits,
  handleRepositoriesGetPullRequestFiles,
  handleReviewsGetWorkspace,
  handleReviewsListReviews,
  handleReviewsSaveDraft,
  handleUtilsPreviewMarkdown,
} from "@/client/msw.gen"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import { comparisonFixture } from "./diff-fixtures"
import { PullRequestDetailView } from "./PullRequestDetail"
import { PullRequestFiles } from "./PullRequestFiles"
import { trackerPulls } from "./tracker-story-fixtures"

const pull = {
  ...trackerPulls[0],
  body: "This change improves keyboard navigation and preserves focus when switching between files.",
  body_html: "<p>This change improves keyboard navigation and preserves focus when switching between files.</p>",
}
const commits = [
  {
    sha: "a".repeat(40),
    author: "alice",
    author_email: "",
    timestamp: 1791712800,
    message: "Preserve focus when switching files",
  },
  {
    sha: "b".repeat(40),
    author: "bob",
    author_email: "",
    timestamp: 1791799200,
    message: "Add keyboard navigation coverage",
  },
]
const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/Pull request detail",
  parameters: {
    msw: {
      handlers: [
        handleRepositoriesGetPullRequest({ body: pull }),
        handleRepositoriesGetPullRequestFiles({ body: comparisonFixture }),
        handleRepositoriesGetPullRequestCommits({ body: { data: commits, count: 2, ref: pull.head_branch } }),
        handleCommentsListComments({
          body: {
            data: [
              {
                id: "comment-1",
                author_username: "bob",
                body: "Thanks for adding keyboard support.",
                body_html: "<p>Thanks for adding keyboard support.</p>",
                created_at: "2026-10-13T12:00:00Z",
                updated_at: "2026-10-13T12:00:00Z",
              },
            ],
            count: 1,
          },
        }),
        handleReviewsListReviews({ body: [] }),
        handleReviewsGetWorkspace({ body: { draft: null, reviewed_paths: [] } }),
        handleReviewsSaveDraft(async ({ request }) =>
          HttpResponse.json({ draft: await request.json(), reviewed_paths: [] }),
        ),
        handleUtilsPreviewMarkdown({ body: "<p>A preview of your comment.</p>" }),
      ],
    },
  },
} satisfies Meta
export default meta
type Story = StoryObj
export const ConversationAndCommits: Story = {
  render: () => <PullRequestDetailView owner="jan-mue" repo="gitedge" prNumber={1} />,
}
const reviews: ReviewPublic[] = [
  {
    id: "requested",
    author_username: "bob",
    state: "changes_requested",
    body: "",
    comments: [],
    base_commit: comparisonFixture.base_commit!,
    head_commit: comparisonFixture.head_commit!,
    created_at: "2026-10-14T12:00:00Z",
  },
  {
    id: "approved",
    author_username: "carol",
    state: "approved",
    body: "",
    comments: [],
    base_commit: comparisonFixture.base_commit!,
    head_commit: comparisonFixture.head_commit!,
    created_at: "2026-10-15T12:00:00Z",
  },
]
export const ReviewStatuses: Story = {
  ...ConversationAndCommits,
  parameters: { msw: { handlers: [handleReviewsListReviews({ body: reviews }), ...meta.parameters.msw.handlers] } },
}
export const Merged: Story = {
  ...ConversationAndCommits,
  parameters: {
    msw: {
      handlers: [
        handleRepositoriesGetPullRequest({ body: { ...pull, state: "merged" } }),
        handleReviewsListReviews({ body: reviews }),
        ...meta.parameters.msw.handlers,
      ],
    },
  },
}
export const Closed: Story = {
  ...ConversationAndCommits,
  parameters: {
    msw: {
      handlers: [
        handleRepositoriesGetPullRequest({ body: { ...pull, state: "closed" } }),
        ...meta.parameters.msw.handlers,
      ],
    },
  },
}
export const ReviewDropdown: Story = {
  render: () => (
    <PullRequestFiles
      owner="jan-mue"
      repo="gitedge"
      number={1}
      changes={comparisonFixture}
      reviews={[]}
      username="reviewer"
      author="alice"
      isOpen
    />
  ),
}
