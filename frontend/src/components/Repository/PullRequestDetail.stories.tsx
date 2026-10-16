import type { Meta, StoryObj } from "@storybook/react-vite"
import { useQuery } from "@tanstack/react-query"
import { HttpResponse } from "msw"
import type { ReviewPublic } from "@/client"
import { reviewsListReviewsOptions } from "@/client/@tanstack/react-query.gen"
import {
  handleCommentsListComments,
  handleRepositoriesGetDiffFile,
  handleRepositoriesGetPullRequest,
  handleRepositoriesGetPullRequestCommits,
  handleRepositoriesGetPullRequestEvents,
  handleRepositoriesGetPullRequestFiles,
  handleReviewsGetCommentContext,
  handleReviewsGetWorkspace,
  handleReviewsListReviews,
  handleReviewsReplyToReview,
  handleReviewsSaveDraft,
  handleUtilsPreviewMarkdown,
} from "@/client/msw.gen"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import { comparisonFixture } from "./diff-fixtures"
import { PullRequestDetailView } from "./PullRequestDetail"
import { PullRequestFiles, ReviewTimeline } from "./PullRequestFiles"
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
        handleRepositoriesGetPullRequestEvents({ body: [] }),
        handleRepositoriesGetDiffFile({ body: comparisonFixture.files[0] }),
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
        handleReviewsGetCommentContext({ body: comparisonFixture.files[0].hunks![0] }),
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
        handleRepositoriesGetPullRequestEvents({
          body: [
            { id: "merge-1", kind: "pull_request_merge", actor_username: "alice", created_at: "2026-10-16T12:00:00Z" },
          ],
        }),
        handleReviewsListReviews({ body: reviews }),
        ...meta.parameters.msw.handlers,
      ],
    },
  },
}
export const AfterMerge: Story = {
  ...ConversationAndCommits,
  parameters: {
    msw: {
      handlers: [
        handleRepositoriesGetPullRequest({ body: { ...pull, state: "merged", updated_at: "2026-10-18T12:00:00Z" } }),
        handleRepositoriesGetPullRequestEvents({
          body: [
            { id: "merge-1", kind: "pull_request_merge", actor_username: "alice", created_at: "2026-10-16T12:00:00Z" },
          ],
        }),
        handleCommentsListComments({
          body: {
            data: [
              {
                id: "before-merge",
                author_username: "bob",
                body: "Ready to merge.",
                body_html: "<p>Ready to merge.</p>",
                created_at: "2026-10-15T12:00:00Z",
                updated_at: "2026-10-15T12:00:00Z",
              },
              {
                id: "after-merge",
                author_username: "carol",
                body: "Thanks for merging!",
                body_html: "<p>Thanks for merging!</p>",
                created_at: "2026-10-17T12:00:00Z",
                updated_at: "2026-10-17T12:00:00Z",
              },
            ],
            count: 2,
          },
        }),
        ...meta.parameters.msw.handlers,
      ],
    },
  },
}
export const ReviewComments: Story = {
  ...ConversationAndCommits,
  parameters: {
    msw: {
      handlers: [
        handleReviewsListReviews({
          body: [
            {
              ...reviews[0],
              id: "context-review",
              comments: [
                { path: "src/config.py", side: "old", line: 1, body: "Why was the previous timeout changed?" },
                { path: "src/config.py", side: "new", line: 1, body: "Please cover this value in a test." },
              ],
            },
            {
              ...reviews[1],
              id: "outdated-review",
              head_commit: "c".repeat(40),
              outdated: true,
              comments: [
                { path: "src/config.py", side: "new", line: 1, body: "This was reviewed on the earlier revision." },
              ],
            },
          ],
        }),
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

const DiscussionExample = () => {
  const { data } = useQuery(reviewsListReviewsOptions({ path: { owner: "jan-mue", repo: "gitedge", number: 1 } }))
  return <ReviewTimeline owner="jan-mue" repo="gitedge" number={1} reviews={data ?? []} username="alice" />
}
let replyReview: ReviewPublic = {
  ...reviews[0],
  id: "reply-review",
  body: "Please explain the timeout change.",
  comments: [
    {
      path: "src/config.py",
      side: "new",
      line: 1,
      body: "Please cover this in a test.",
      context: comparisonFixture.files[0].hunks![0],
    },
  ],
  replies: [],
}
export const ReviewDiscussion: Story = {
  render: () => <DiscussionExample />,
  parameters: {
    msw: {
      handlers: [
        handleReviewsListReviews(() => HttpResponse.json([replyReview])),
        handleReviewsReplyToReview(async ({ request }) => {
          const body = (await request.json()) as { body: string; comment_index: number | null }
          const reply = {
            ...body,
            id: `reply-${replyReview.replies?.length ?? 0}`,
            author_username: "alice",
            created_at: "2026-10-16T12:00:00Z",
            body_html: `<p>${body.body.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</p>`,
          }
          replyReview = { ...replyReview, replies: [...(replyReview.replies ?? []), reply] }
          return HttpResponse.json(reply, { status: 201 })
        }),
        ...meta.parameters.msw.handlers,
      ],
    },
  },
}
