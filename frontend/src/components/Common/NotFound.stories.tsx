import type { Meta, StoryObj } from "@storybook/react-vite"
import NotFound from "@/components/Common/NotFound"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Not found" } satisfies Meta
export default meta
type Story = StoryObj

export const NotFoundPage: Story = { render: () => <NotFound /> }
