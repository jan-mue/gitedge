import { useQuery } from "@tanstack/react-query"
import { GitMerge, MessageSquare, Users } from "lucide-react"
import type { ReactNode } from "react"
import type { CompareResult, PullRequestPublic, ReviewPublic } from "@/client"
import {
  commentsListCommentsOptions,
  repositoriesGetPullRequestEventsOptions,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  ConversationCard,
  ConversationItem,
  MarkdownContent,
  ReviewStatusIcon,
  Link as RouterLink,
} from "@/components/design-system"
import { CommentsSection } from "./CommentsSection"
import { ReviewTimeline } from "./PullRequestFiles"

export const PullRequestConversation = ({
  owner,
  repo,
  pull,
  reviews,
  changes,
  mergeActions,
  closeActions,
  username,
}: {
  owner: string
  repo: string
  pull: PullRequestPublic
  reviews: ReviewPublic[]
  changes?: CompareResult
  mergeActions: ReactNode
  closeActions: ReactNode
  username?: string
}) => {
  const { data: comments } = useQuery({
    ...commentsListCommentsOptions({ path: { owner, repo, number: pull.number } }),
    staleTime: 10_000,
  })
  const {
    data: stateEvents = [],
    isError: eventsError,
    refetch: retryEvents,
  } = useQuery({
    ...repositoriesGetPullRequestEventsOptions({ path: { owner, repo, number: pull.number } }),
    staleTime: 10_000,
  })
  const participants = [
    ...new Set([
      pull.author_username,
      ...reviews.map((review) => review.author_username),
      ...reviews.flatMap((review) => (review.replies ?? []).map((reply) => reply.author_username)),
      ...(comments?.data ?? []).map((comment) => comment.author_username),
    ]),
  ]
  const reviewers = [...new Map(reviews.map((review) => [review.author_username, review])).values()]
  return (
    <div
      className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,1fr)_13rem] lg:grid-cols-[minmax(0,1fr)_16rem]"
      data-testid="pr-conversation"
    >
      <div className="min-w-0 flex-1">
        <CommentsSection
          owner={owner}
          repo={repo}
          number={pull.number}
          author={pull.author_username}
          timeline
          intro={
            <ConversationItem>
              <ConversationCard author={pull.author_username} date={pull.created_at} badge="Author">
                <MarkdownContent html={pull.body_html || "<p>No description provided.</p>"} />
              </ConversationCard>
            </ConversationItem>
          }
          events={[
            ...reviews.map((review) => ({
              id: `review-${review.id}`,
              created_at: review.created_at,
              icon: <ReviewStatusIcon state={review.state} />,
              content: (
                <ReviewTimeline
                  owner={owner}
                  repo={repo}
                  number={pull.number}
                  username={username}
                  reviews={[review]}
                  changes={changes}
                />
              ),
            })),
            ...stateEvents.map((event) => ({
              id: event.id,
              created_at: event.created_at,
              icon:
                event.kind === "pull_request_merge" ? (
                  <ReviewStatusIcon state="merged" />
                ) : event.kind === "pull_request_close" ? (
                  <ReviewStatusIcon state="closed" />
                ) : (
                  <ReviewStatusIcon state="reopened" />
                ),
              content: (
                <div
                  className="flex flex-wrap items-center gap-x-1.5 gap-y-1 min-h-8 text-sm text-muted-foreground"
                  data-testid={`pr-event-${event.kind}`}
                >
                  <strong className="font-medium text-foreground">{event.actor_username}</strong>
                  {event.kind === "pull_request_merge" && pull.merged_commit_id ? (
                    <>
                      <span>merged commit</span>
                      <RouterLink
                        to="/$owner/$repo/commit/$hash"
                        params={{ owner, repo, hash: pull.merged_commit_id }}
                        appearance="muted"
                      >
                        <code className="rounded border border-border bg-secondary px-1.5 py-0.5 text-xs">
                          {pull.merged_commit_id.slice(0, 10)}
                        </code>
                      </RouterLink>
                      <span>into</span>
                      <code className="rounded bg-secondary px-1 text-xs">{pull.base_branch}</code>
                    </>
                  ) : (
                    <span>
                      {event.kind === "pull_request_merge"
                        ? "merged this pull request"
                        : event.kind === "pull_request_close"
                          ? "closed this pull request"
                          : "reopened this pull request"}
                    </span>
                  )}
                  <time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time>
                </div>
              ),
            })),
          ]}
          beforeComposer={
            <>
              {eventsError && (
                <p role="alert" className="mb-4 text-sm">
                  Unable to load pull request events.{" "}
                  <Button variant="text" size="text" onClick={() => retryEvents()}>
                    Retry
                  </Button>
                </p>
              )}
              {pull.state === "open" && (
                <ConversationItem icon={<GitMerge className="size-4 shrink-0" />}>
                  <div className="rounded-lg border border-border bg-secondary/30 p-4">
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-medium">
                      <GitMerge className="size-4 text-success" />
                      Merge pull request
                    </h3>
                    <p className="mb-3 break-words text-sm text-muted-foreground">
                      Changes from <code>{pull.head_branch}</code> into <code>{pull.base_branch}</code>.
                    </p>
                    <div className="flex flex-wrap gap-2">{mergeActions}</div>
                  </div>
                </ConversationItem>
              )}
            </>
          }
          actions={closeActions}
        />
      </div>
      <aside className="min-w-0 space-y-4" aria-label="Pull request details">
        <SidebarSection title="Reviewers">
          {reviewers.length ? (
            reviewers.map((review) => (
              <div key={review.author_username} className="flex items-center gap-2 py-1 text-sm text-muted-foreground">
                <ReviewStatusIcon state={review.state} inline />
                <span>
                  {review.author_username}{" "}
                  {review.state === "approved"
                    ? "approved these changes"
                    : review.state === "changes_requested"
                      ? "requested changes"
                      : "reviewed with comments"}
                </span>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No reviewers</p>
          )}
        </SidebarSection>
        <SidebarSection title="Labels">
          <p className="text-sm text-muted-foreground">No labels</p>
        </SidebarSection>
        <SidebarSection title="Milestone">
          <p className="text-sm text-muted-foreground">No milestone</p>
        </SidebarSection>
        <SidebarSection title="Assignees">
          <p className="text-sm text-muted-foreground">No assignees</p>
        </SidebarSection>
        <SidebarSection title={`${participants.length} participants`}>
          <div className="flex flex-wrap gap-1">
            {participants.map((name) => (
              <span
                key={name}
                title={name}
                className="flex size-7 items-center justify-center rounded-full bg-accent text-xs font-medium text-accent-foreground"
              >
                {name.charAt(0).toUpperCase()}
              </span>
            ))}
          </div>
        </SidebarSection>
        <SidebarSection title="Reference">
          <p className="break-all font-mono text-xs text-muted-foreground">
            {owner}/{repo}!{pull.number}
          </p>
        </SidebarSection>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <MessageSquare className="size-3.5" />
          {comments?.count ?? 0} comments <Users className="ml-auto size-3.5" />
          {participants.length}
        </div>
      </aside>
    </div>
  )
}

const SidebarSection = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="border-b border-border pb-3">
    <h3 className="mb-2 text-sm font-medium">{title}</h3>
    {children}
  </section>
)
