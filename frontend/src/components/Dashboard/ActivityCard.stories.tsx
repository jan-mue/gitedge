import type { Meta, StoryObj } from "@storybook/react-vite"
import type { ActivityPublic } from "@/client"
import { StoryRouter } from "@/components/Storybook/StoryRouter"
import { ActivityCard } from "./ActivityCard"

const activity: ActivityPublic = {
  id: "star-activity",
  kind: "star",
  actor_username: "alex",
  repo_owner: "jan-mue",
  repo_name: "gitedge",
  target_type: "repository",
  created_at: "2026-10-12T12:00:00Z",
}
const meta = {
  title: "Patterns/Dashboard/Activity card",
  component: ActivityCard,
  decorators: [
    (Story) => (
      <StoryRouter>
        <Story />
      </StoryRouter>
    ),
  ],
  args: { activity },
} satisfies Meta<typeof ActivityCard>
export default meta
type Story = StoryObj<typeof meta>
export const Star: Story = {}
export const OpenIssue: Story = {
  args: {
    activity: {
      ...activity,
      id: "issue-activity",
      kind: "issue_open",
      title: "Improve repository navigation",
      target_type: "issue",
      target_number: 42,
      preview: { state: "open", body: "Keep the interface **compact** and easy to navigate.", comments_count: 3 },
    },
  },
}
export const MergedPullRequest: Story = {
  args: {
    activity: {
      ...activity,
      id: "merge-activity",
      kind: "pull_request_merge",
      title: "Restore the reference palette",
      target_type: "pull_request",
      target_number: 43,
      preview: { state: "merged", body: "Use semantic tokens for the original colors.", comments_count: 2 },
    },
  },
}
export const Comment: Story = {
  args: {
    activity: {
      ...activity,
      id: "comment-activity",
      kind: "comment",
      title: "Review component states",
      target_type: "issue",
      target_number: 42,
      preview: {
        state: "open",
        body: "Review the keyboard, hover, disabled, and loading states before changing a component. ".repeat(6),
        body_truncated: true,
        comments_count: 4,
      },
    },
  },
}
export const RepositoryUnavailable: Story = {
  args: { activity: { ...activity, id: "unavailable-activity", repo_owner: null, repo_name: null } },
}
