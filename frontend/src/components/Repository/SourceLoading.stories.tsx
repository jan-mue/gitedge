import type { Meta, StoryObj } from "@storybook/react-vite"
import SourceLoading from "@/components/Repository/SourceLoading"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Source loading" } satisfies Meta
export default meta
type Story = StoryObj

export const FileSkeleton: Story = { render: () => <SourceLoading kind="blob" /> }
export const DirectorySkeleton: Story = { render: () => <SourceLoading kind="tree" /> }
export const PathSkeleton: Story = { render: () => <SourceLoading /> }
