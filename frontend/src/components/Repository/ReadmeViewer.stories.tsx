import type { Meta, StoryObj } from "@storybook/react-vite"
import ReadmeViewer from "@/components/Repository/ReadmeViewer"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"

const meta = { ...repositoryStoryMeta, title: "Patterns/Repository/README" } satisfies Meta
export default meta
type Story = StoryObj

export const Readme: Story = {
  render: () => (
    <ReadmeViewer
      content=""
      html={
        "<h1>GitEdge</h1><p>Git hosting at the <strong>edge</strong>. Built for developers.</p><h2>Getting started</h2><pre><code>git clone https://gitedge-app.vercel.app/jan-mue/gitedge.git</code></pre><ul><li>Blob-backed Git objects</li><li>Fast repository browsing</li></ul><blockquote>Push your code. Keep moving.</blockquote><table><thead><tr><th>Feature</th><th>Status</th></tr></thead><tbody><tr><td>Repository browsing</td><td>Available</td></tr></tbody></table>"
      }
    />
  ),
}
export const ReadmeFallback: Story = {
  render: () => <ReadmeViewer content="# GitEdge\n\nGit hosting at the edge." html="" />,
}
