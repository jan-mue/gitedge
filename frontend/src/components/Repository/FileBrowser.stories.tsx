import type { Meta, StoryObj } from "@storybook/react-vite"
import FileBrowser from "@/components/Repository/FileBrowser"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Files" } satisfies Meta
export default meta
type Story = StoryObj

export const FileTree: Story = {
  render: () => (
    <FileBrowser
      owner="jan-mue"
      repo="gitedge"
      entries={[
        { name: "frontend", path: "frontend", type: "tree" },
        { name: "backend", path: "backend", type: "tree" },
        { name: "README.md", path: "README.md", type: "blob", size: 4096 },
        { name: "bun.lock", path: "bun.lock", type: "blob", size: 62000 },
      ]}
      lastCommit={{
        sha: "ce65263abc123456",
        author: "Jan",
        message: "Build the GitEdge design system",
        timestamp: 1791756000,
      }}
    />
  ),
}
export const NestedTree: Story = {
  render: () => (
    <FileBrowser
      owner="jan-mue"
      repo="gitedge"
      treePath="frontend/src"
      lastCommit={{
        sha: "77ddec2ecc829b765bef3ee2674b42246d1d6fba",
        author: "Jan Müller",
        message: "Fix repository browsing",
        timestamp: 1791663993,
      }}
      entries={[
        { name: "components", path: "frontend/src/components", type: "tree" },
        { name: "main.tsx", path: "frontend/src/main.tsx", type: "blob", size: 2048 },
      ]}
    />
  ),
}
export const EmptyTree: Story = { render: () => <FileBrowser owner="jan-mue" repo="gitedge" entries={[]} /> }
