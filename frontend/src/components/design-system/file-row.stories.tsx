import type { Meta, StoryObj } from "@storybook/react-vite"
import { FileText } from "lucide-react"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import { FileRow } from "./file-row"
import { Link } from "./link"

const meta = {
  ...repositoryStoryMeta,
  title: "Components/File Row",
  component: FileRow,
} satisfies Meta<typeof FileRow>
export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <FileRow>
      <Link
        to="/$owner/$repo/src/branch/$branch/$"
        params={{ owner: "jan-mue", repo: "gitedge", branch: "main", _splat: "README.md" }}
        appearance="fileEntry"
      >
        <FileText aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
        <span>README.md</span>
      </Link>
      <Link
        to="/$owner/$repo/commit/$hash"
        params={{ owner: "jan-mue", repo: "gitedge", hash: "77ddec2ecc829b765bef3ee2674b42246d1d6fba" }}
        appearance="fileCommit"
      >
        Document development commands
      </Link>
      <time className="whitespace-nowrap text-xs text-muted-foreground sm:text-sm" dateTime="2026-10-10T20:26:33Z">
        2 days ago
      </time>
    </FileRow>
  ),
}
