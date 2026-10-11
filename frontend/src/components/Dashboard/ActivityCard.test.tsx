import type { ComponentPropsWithRef } from "react"
import { describe, expect, test, vi } from "vitest"
import type { ActivityPublic } from "@/client"
import { render, screen } from "@/test/test-utils"
import ActivityCard from "./ActivityCard"

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, params, ...props }: ComponentPropsWithRef<"a"> & { to: string; params: Record<string, string> }) => (
    <a {...props} href={to.replace(/\$(\w+)/g, (_, key: string) => params[key])} />
  ),
}))
const activity: ActivityPublic = {
  id: "event-1",
  actor_username: "alice",
  repo_owner: "owner",
  repo_name: "repo",
  title: "A better feed",
  kind: "pull_request_merge",
  target_type: "pull_request",
  target_number: 17,
  created_at: new Date(Date.now() - 600_000).toISOString(),
  preview: {
    body: `## Summary\nUse \`explicit origins\`.\n\n${"Description ".repeat(30)}THE END`,
    state: "merged",
    comments_count: 3,
  },
}

describe("ActivityCard", () => {
  test("links real users and targets, shows status and comments, and expands descriptions", async () => {
    const { user } = render(<ActivityCard activity={activity} />)
    expect(screen.getByRole("link", { name: "alice" })).toHaveAttribute("href", "/profile/alice")
    expect(screen.getByRole("link", { name: "A better feed #17" })).toHaveAttribute("href", "/owner/repo/pulls/17")
    expect(screen.getByText("Merged")).toBeInTheDocument()
    expect(screen.getByText("10 minutes ago")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "3 comments" })).toHaveAttribute("href", "/owner/repo/pulls/17")
    expect(screen.getByText("explicit origins").tagName).toBe("CODE")
    expect(screen.queryByText(/THE END/)).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Read more" }))
    expect(screen.getByText(/THE END/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Show less" })).toHaveAttribute("aria-expanded", "true")
    await user.click(screen.getByRole("button", { name: "Show less" }))
    expect(screen.queryByText(/THE END/)).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Activity options" }))
    expect(screen.getByRole("menuitem", { name: "View activity" })).toHaveAttribute("href", "/owner/repo/pulls/17")
  })
  test("renders issue previews as text without interpreting raw HTML", () => {
    const { container } = render(
      <ActivityCard
        activity={{
          ...activity,
          kind: "issue_open",
          target_type: "issue",
          preview: { body: '<script>alert("bad")</script>', state: "closed", comments_count: 0 },
        }}
      />,
    )
    expect(screen.getByRole("link", { name: "A better feed #17" })).toHaveAttribute("href", "/owner/repo/issues/17")
    expect(screen.getByText("Closed")).toBeInTheDocument()
    expect(container.querySelector("script")).toBeNull()
    expect(screen.getByText('<script>alert("bad")</script>')).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Read more" })).not.toBeInTheDocument()
  })
  test("keeps events without target previews useful", () => {
    render(
      <ActivityCard
        activity={{
          ...activity,
          kind: "star",
          target_type: "repository",
          target_number: null,
          title: "repo",
          preview: null,
        }}
      />,
    )
    expect(screen.getByRole("link", { name: "repo" })).toHaveAttribute("href", "/owner/repo")
    expect(screen.queryByText("Merged")).not.toBeInTheDocument()
    expect(screen.queryByText("Join the discussion")).not.toBeInTheDocument()
  })
})
