import type { IssuePublic, PullRequestPublic } from "@/client"

export const trackerIssues: IssuePublic[] = [
  {
    id: "issue-1",
    number: 1,
    title: "Improve keyboard navigation in repository lists",
    state: "open",
    author_username: "alice",
    created_at: "2026-10-01T10:00:00Z",
    updated_at: "2026-10-12T10:00:00Z",
    repo_owner: "jan-mue",
    repo_name: "gitedge",
    body_html: "",
  },
  {
    id: "issue-2",
    number: 2,
    title: "Make repository filters easier to discover",
    state: "open",
    author_username: "bob",
    created_at: "2026-10-02T10:00:00Z",
    updated_at: "2026-10-03T10:00:00Z",
    repo_owner: "jan-mue",
    repo_name: "gitedge",
    body_html: "",
  },
  {
    id: "issue-3",
    number: 3,
    title: "Restore contextual action styles",
    state: "closed",
    author_username: "alice",
    created_at: "2026-10-03T10:00:00Z",
    updated_at: "2026-10-04T10:00:00Z",
    repo_owner: "jan-mue",
    repo_name: "gitedge",
    body_html: "",
  },
]
export const trackerPulls: PullRequestPublic[] = trackerIssues.map((issue, index) => ({
  ...issue,
  id: `pull-${issue.number}`,
  title: ["Improve keyboard navigation", "Add repository filters", "Restore contextual action styles"][index],
  state: index === 2 ? "merged" : "open",
  head_branch: ["keyboard-navigation", "repository-filters", "contextual-styles"][index],
  base_branch: index === 1 ? "develop" : "main",
}))
