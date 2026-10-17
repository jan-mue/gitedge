import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import { handleRepositoriesGetDiffFile } from "@/client/msw.gen"
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
export const Loading: Story = {
  args: {
    files: comparisonFixture.files.map((file) => ({ ...file, diff_loaded: false, hunks: [], diff_line_count: 12 })),
    diffSource: { owner: "owner", repo: "repo", base: "a".repeat(40), head: "b".repeat(40) },
  },
  parameters: {
    msw: {
      handlers: [
        handleRepositoriesGetDiffFile(async () => {
          await delay(120000)
          return HttpResponse.json(comparisonFixture.files[0])
        }),
      ],
    },
  },
}
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
