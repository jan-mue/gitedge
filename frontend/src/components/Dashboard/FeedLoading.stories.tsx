import type { Meta, StoryObj } from "@storybook/react-vite"
import FeedLoading from "@/components/Dashboard/FeedLoading"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Dashboard/Feed loading" } satisfies Meta
export default meta
type Story = StoryObj

export const FeedSkeleton: Story = { render: () => <FeedLoading /> }
