import type { Meta, StoryObj } from "@storybook/react-vite"
import ActivityLoading from "@/components/Repository/ActivityLoading"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Activity loading" } satisfies Meta
export default meta
type Story = StoryObj

export const ActivitySkeleton: Story = { render: () => <ActivityLoading view="pulse" /> }
export const ContributorSkeleton: Story = { render: () => <ActivityLoading view="contributors" /> }
export const FrequencySkeleton: Story = { render: () => <ActivityLoading view="code-frequency" /> }
export const CommitsSkeleton: Story = { render: () => <ActivityLoading view="recent-commits" /> }
