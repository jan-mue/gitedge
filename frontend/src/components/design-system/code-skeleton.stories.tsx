import type { Meta, StoryObj } from "@storybook/react-vite"
import { CodeSkeleton } from "./code-skeleton"

const meta = { title: "Components/Code skeleton", component: CodeSkeleton } satisfies Meta<typeof CodeSkeleton>
export default meta
type Story = StoryObj<typeof meta>
export const Loading: Story = { args: { lineCount: 12 } }
