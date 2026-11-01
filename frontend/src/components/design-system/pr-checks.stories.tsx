import type { Meta, StoryObj } from "@storybook/react-vite"
import { ExternalLink } from "./link"
import { PullRequestChecks } from "./pr-checks"

const meta = {
  title: "Components/PR checks",
  component: PullRequestChecks,
  args: {
    revision: "b47bca7d29b635d352e1186f3c68712f7705a331",
    checks: [
      {
        id: "test-24",
        name: "CI / Tests (node: 24)",
        status: "success",
        duration: "12s",
        details: (
          <ExternalLink href="/octocat/hello-world/actions?run=example" appearance="caption">
            Details
          </ExternalLink>
        ),
      },
      { id: "test-22", name: "CI / Tests (node: 22)", status: "success", duration: "14s" },
      { id: "lint", name: "CI / Lint", status: "success", duration: "3s" },
    ],
  },
} satisfies Meta<typeof PullRequestChecks>
export default meta
type Story = StoryObj<typeof meta>

export const Successful: Story = {}
export const Running: Story = {
  args: {
    checks: [
      { id: "test", name: "CI / Tests", status: "running", duration: "8s" },
      { id: "deploy", name: "Preview / Deploy", status: "queued" },
    ],
  },
}
export const Failed: Story = {
  args: {
    checks: [
      { id: "lint", name: "CI / Lint", status: "failure", duration: "4s" },
      { id: "test", name: "CI / Tests", status: "success", duration: "12s" },
      { id: "deploy", name: "Preview / Deploy", status: "skipped" },
    ],
  },
}
export const Cancelled: Story = {
  args: { checks: [{ id: "test", name: "CI / Tests", status: "cancelled", duration: "8s" }] },
}
export const Empty: Story = { args: { checks: [] } }
export const Loading: Story = { args: { checks: [], loading: true, revision: undefined } }
export const Unavailable: Story = { args: { checks: [], error: "Unable to load workflow results.", retry: () => {} } }
