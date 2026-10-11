import type { BranchInfo, IssuePublic, PullRequestPublic } from "@/client"

export const branches: BranchInfo[] = [
  { name: "main", is_default: true },
  { name: "feature", is_default: false },
]

export const issue: IssuePublic = {
  id: "1",
  repo_owner: "owner",
  repo_name: "repo",
  number: 1,
  title: "First issue",
  body: null,
  body_html: "",
  state: "open",
  author_username: "owner",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

export const pullRequest: PullRequestPublic = {
  ...issue,
  title: "First pull request",
  head_branch: "feature",
  base_branch: "main",
  merge_base: null,
  merged_commit_id: null,
  has_merged: false,
}
