import type { Meta, StoryObj } from "@storybook/react-vite"
import ErrorComponent from "@/components/Common/ErrorComponent"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Error" } satisfies Meta
export default meta
type Story = StoryObj

export const ErrorPage: Story = { render: () => <ErrorComponent /> }
