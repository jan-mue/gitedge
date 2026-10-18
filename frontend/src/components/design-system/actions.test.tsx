import userEvent from "@testing-library/user-event"
import { describe, expect, test } from "vitest"
import { render, screen } from "@/test/test-utils"
import { LogViewer } from "./log-viewer"
import { PullRequestChecks } from "./pr-checks"

describe("Pull request checks", () => {
  test("reports pending checks and collapses real job rows", async () => {
    const user = userEvent.setup()
    render(<PullRequestChecks checks={[{ id: "test", name: "CI / Tests", status: "running" }]} />)
    const button = screen.getByRole("button", { name: /Checks are running/ })
    expect(button).toHaveAttribute("aria-expanded", "true")
    await user.click(button)
    expect(screen.queryByText("CI / Tests")).not.toBeInTheDocument()
    await user.click(button)
    expect(screen.getByText("CI / Tests")).toBeInTheDocument()
  })
  test("does not report success for skipped or absent checks", () => {
    render(<PullRequestChecks checks={[{ id: "test", name: "CI / Tests", status: "skipped" }]} />)
    expect(screen.getByText("All checks were skipped")).toBeInTheDocument()
    expect(screen.queryByText("All checks were successful")).not.toBeInTheDocument()
    expect(screen.queryByText("Required")).not.toBeInTheDocument()
  })
})

describe("Log viewer", () => {
  test("opens failed steps and renders untrusted logs as text", async () => {
    const user = userEvent.setup()
    const log = '<script>alert("untrusted")</script>'
    const { container } = render(<LogViewer sections={[{ id: "test", name: "Tests", status: "failure", log }]} />)
    expect(screen.getByText(log)).toBeInTheDocument()
    expect(container.querySelector("script")).toBeNull()
    await user.click(screen.getByRole("button", { name: /Tests/ }))
    expect(screen.queryByText(log)).not.toBeInTheDocument()
  })
})
