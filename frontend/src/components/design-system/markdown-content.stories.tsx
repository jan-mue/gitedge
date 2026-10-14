import type { Meta, StoryObj } from "@storybook/react-vite"
import MarkdownContent from "./markdown-content"

const meta = { title: "Components/Markdown content" } satisfies Meta
export default meta
type Story = StoryObj
export const Readme: Story = {
  render: () => (
    <MarkdownContent html="<h1>GitEdge</h1><p>Git hosting at the <strong>edge</strong>.</p><h2>Getting started</h2><pre><code>git clone https://gitedge.dev/gitedge/gitedge.git</code></pre><ul><li>Browse repositories</li><li>Track issues</li></ul>" />
  ),
}
export const Empty: Story = { render: () => <MarkdownContent html="" /> }
