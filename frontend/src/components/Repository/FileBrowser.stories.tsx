import type { Meta, StoryObj } from "@storybook/react-vite"
import FileBrowser from "@/components/Repository/FileBrowser"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/Files" } satisfies Meta
export default meta
type Story = StoryObj

const sourceCommit = {
  sha: "77ddec2ecc829b765bef3ee2674b42246d1d6fba",
  author: "Jan",
  message: "Improve repository browsing",
  timestamp: 1791663993,
}
const docsCommit = {
  ...sourceCommit,
  sha: "ce65263abc123456",
  message: "Document development commands",
  timestamp: 1791756000,
}

export const FileTree: Story = {
  render: () => (
    <FileBrowser
      owner="jan-mue"
      repo="gitedge"
      entries={[
        { name: "frontend", path: "frontend", type: "tree", last_commit: sourceCommit },
        { name: "backend", path: "backend", type: "tree", last_commit: sourceCommit },
        { name: "README.md", path: "README.md", type: "blob", size: 4096, last_commit: docsCommit },
        { name: "bun.lock", path: "bun.lock", type: "blob", size: 62000, last_commit: docsCommit },
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
        { name: "components", path: "frontend/src/components", type: "tree", last_commit: sourceCommit },
        { name: "main.tsx", path: "frontend/src/main.tsx", type: "blob", size: 2048, last_commit: sourceCommit },
      ]}
    />
  ),
}
export const EmptyTree: Story = { render: () => <FileBrowser owner="jan-mue" repo="gitedge" entries={[]} /> }
export const LongNames: Story = {
  render: () => (
    <FileBrowser
      owner="jan-mue"
      repo="gitedge"
      lastCommit={sourceCommit}
      entries={[
        {
          name: "a-very-long-directory-name-that-must-fit-on-mobile",
          path: "a-very-long-directory-name-that-must-fit-on-mobile",
          type: "tree",
          last_commit: {
            ...sourceCommit,
            message: "Improve repository browsing and preserve navigation across all revisions",
          },
        },
        {
          name: "a-very-long-file-name-with-a-long-extension.test.tsx",
          path: "a-very-long-file-name-with-a-long-extension.test.tsx",
          type: "blob",
          size: 8192,
          last_commit: docsCommit,
        },
      ]}
    />
  ),
}
