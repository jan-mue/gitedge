import type { Meta, StoryObj } from "@storybook/react-vite"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import RepositoryCommitHeader from "./RepositoryCommitHeader"

const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/Commit header",
  component: RepositoryCommitHeader,
  args: { owner: "jan-mue", repo: "gitedge" },
} satisfies Meta<typeof RepositoryCommitHeader>
export default meta
type Story = StoryObj<typeof meta>
export const LatestCommit: Story = {
  args: {
    commit: {
      sha: "77ddec2ecc829b765bef3ee2674b42246d1d6fba",
      author: "Jan Müller",
      message: "Fix Git HTTP routing and chunked pushes (#253)",
      timestamp: 1791663993,
    },
  },
}
export const Loading: Story = { args: { loading: true } }
export const LoadError: Story = { args: { error: true, onRetry: () => {} } }
