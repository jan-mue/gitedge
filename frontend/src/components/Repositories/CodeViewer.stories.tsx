import type { Meta, StoryObj } from "@storybook/react-vite"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import CodeViewer from "./CodeViewer"

const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Repository/File contents",
  component: CodeViewer,
  args: {
    file: {
      name: "main.ts",
      path: "src/main.ts",
      size: 31,
      content: 'export const name = "GitEdge"\n',
      highlighted_html: '<pre class="highlight"><code>export const name = "GitEdge"</code></pre>',
      css: ".highlight { padding: 1rem; }",
      css_dark: "",
      language: "TypeScript",
      line_count: 1,
      last_commit: {
        sha: "77ddec2ecc829b765bef3ee2674b42246d1d6fba",
        author: "Jan",
        message: "Initialize the application",
        timestamp: 1791663993,
      },
    },
    commitSha: "ce65263abc12345678901234567890123456789012",
    backLink: { owner: "jan-mue", repo: "gitedge", mode: "branch", refName: "main", path: "src" },
  },
} satisfies Meta<typeof CodeViewer>
export default meta
type Story = StoryObj<typeof meta>
export const SourceFile: Story = {}
export const TaggedFile: Story = { args: { backLink: { ...meta.args.backLink, mode: "tag", refName: "v1.0.0" } } }
export const LongCommitMessage: Story = {
  args: {
    file: {
      ...meta.args.file,
      last_commit: {
        ...meta.args.file.last_commit,
        message:
          "Preserve file navigation and immutable revision links when browsing long directory paths\n\nCommit details.",
      },
    },
  },
}
