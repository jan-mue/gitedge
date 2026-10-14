import type { Meta, StoryObj } from "@storybook/react-vite"

const meta = { title: "Foundations/Tokens" } satisfies Meta
export default meta
type Story = StoryObj

export const ColorTokens: Story = {
  render: () => (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[
        ["background", "bg-background text-foreground", "Page canvas"],
        ["card", "bg-card text-card-foreground", "Content surfaces"],
        ["popover", "bg-popover text-popover-foreground", "Menus and dialogs"],
        ["primary", "bg-primary text-primary-foreground", "Primary action"],
        ["secondary", "bg-secondary text-secondary-foreground", "Secondary surface"],
        ["muted", "bg-muted text-muted-foreground", "Supporting content"],
        ["accent", "bg-accent text-accent-foreground", "Hover and selection"],
        ["success", "bg-success-emphasis text-success-foreground", "Open and created"],
        ["destructive", "bg-destructive-emphasis text-destructive-foreground", "Destructive actions"],
        ["warning", "bg-warning text-warning-foreground", "Attention required"],
        ["info", "bg-info-emphasis text-info-foreground", "Information"],
        ["merged", "bg-merged text-merged-foreground", "Merged pull requests"],
        ["sidebar", "bg-sidebar text-sidebar-foreground", "Navigation surface"],
      ].map(([token, classes, usage]) => (
        <div key={token} className={`rounded-lg border border-border p-5 ${classes}`}>
          <p className="font-mono text-sm font-semibold">{token}</p>
          <p className="mt-1 text-sm">{usage}</p>
        </div>
      ))}
    </div>
  ),
}
export const Typography: Story = {
  render: () => (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Repository heading · Inter</h1>
      <h2 className="text-lg font-semibold">Section heading</h2>
      <p className="text-sm">Body text for repository descriptions, issue titles, and navigation.</p>
      <p className="text-xs text-muted-foreground">Metadata · last updated 2 hours ago</p>
      <code className="font-mono text-sm">git clone https://gitedge-app.vercel.app/jan/gitedge.git</code>
    </div>
  ),
}
