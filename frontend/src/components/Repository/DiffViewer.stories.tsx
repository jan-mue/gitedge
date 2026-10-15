import type { Meta, StoryObj } from "@storybook/react-vite"
import { DiffViewer } from "./DiffViewer"
import { comparisonFixture } from "./diff-fixtures"

const meta = {
  title: "Repository/Diff viewer",
  component: DiffViewer,
  parameters: { layout: "padded" },
  args: comparisonFixture,
} satisfies Meta<typeof DiffViewer>
export default meta
type Story = StoryObj<typeof meta>
export const Default: Story = {}
export const Review: Story = {
  args: {
    reviewedPaths: ["tests/test_config.py"],
    onReviewed: () => {},
    onAddComment: async () => {},
    annotations: [
      {
        id: "comment-1",
        author: "reviewer",
        path: "src/config.py",
        side: "new",
        line: 1,
        body: "Can we document why this timeout changed?",
        pending: true,
      },
    ],
  },
}
