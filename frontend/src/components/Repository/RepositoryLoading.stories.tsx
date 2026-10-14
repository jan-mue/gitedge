import type { Meta, StoryObj } from "@storybook/react-vite"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Loading" } satisfies Meta
export default meta
type Story = StoryObj

export const RepositorySkeleton: Story = { render: () => <RepositoryLoading /> }
export const RetryError: Story = {
  render: () => <RepositoryError message="Unable to load this repository." retry={() => {}} />,
}
