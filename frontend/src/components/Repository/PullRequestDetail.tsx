import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useParams } from "@tanstack/react-router"
import {
  ArrowLeft,
  FileText,
  GitCommitHorizontal,
  GitMerge,
  GitPullRequest,
  GitPullRequestClosed,
  MessageSquare,
} from "lucide-react"
import { useState } from "react"
import {
  commentsListCommentsOptions,
  repositoriesGetPullRequestCommitsOptions,
  repositoriesGetPullRequestEventsQueryKey,
  repositoriesGetPullRequestFilesOptions,
  repositoriesGetPullRequestOptions,
  repositoriesGetPullRequestQueryKey,
  repositoriesListPullRequestsQueryKey,
  repositoriesUpdatePullRequestMutation,
  reviewsListReviewsOptions,
} from "@/client/@tanstack/react-query.gen"
import {
  Badge,
  Button,
  Input,
  Link as RouterLink,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from "@/components/design-system"
import { PullRequestFiles } from "@/components/Repository/PullRequestFiles"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { PullRequestChecks } from "./PullRequestChecks"
import { PullRequestCommits } from "./PullRequestCommits"
import { PullRequestConversation } from "./PullRequestConversation"
import { PullRequestMergeButton } from "./PullRequestMergeButton"

const stateBadge = (state: string) => {
  if (state === "merged") {
    return (
      <Badge variant="merged" data-testid="pr-state">
        <GitMerge className="w-3 h-3" /> Merged
      </Badge>
    )
  }
  if (state === "closed") {
    return (
      <Badge variant="destructive" data-testid="pr-state">
        <GitPullRequestClosed className="w-3 h-3" /> Closed
      </Badge>
    )
  }
  return (
    <Badge variant="success" data-testid="pr-state">
      <GitPullRequest className="w-3 h-3" /> Open
    </Badge>
  )
}

const PullRequestDetail = () => {
  const { owner, repo, number } = useParams({ from: "/_layout/$owner/$repo/pulls/$number" })
  return <PullRequestDetailView owner={owner} repo={repo} prNumber={Number(number)} />
}

export const PullRequestDetailView = ({ owner, repo, prNumber }: { owner: string; repo: string; prNumber: number }) => {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [editing, setEditing] = useState(false)
  const [tab, setTab] = useState("conversation")
  const [editTitle, setEditTitle] = useState("")
  const [editBody, setEditBody] = useState("")

  const {
    data: pull,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesGetPullRequestOptions({ path: { owner, repo, number: prNumber } }),
  })

  const changesQuery = useQuery({
    ...repositoriesGetPullRequestFilesOptions({
      path: { owner, repo, number: prNumber },
      query: { include_diff: false },
    }),
    enabled: tab === "files",
    staleTime: 10_000,
  })

  const commitsQuery = useQuery({
    ...repositoriesGetPullRequestCommitsOptions({
      path: { owner, repo, number: prNumber },
      query: { offset: 0, limit: 50 },
    }),
    enabled: tab === "commits",
    staleTime: 10_000,
  })
  const commentsQuery = useQuery({
    ...commentsListCommentsOptions({ path: { owner, repo, number: prNumber } }),
    staleTime: 10_000,
  })
  const changes = changesQuery.data
  const reviewsQuery = useQuery({
    ...reviewsListReviewsOptions({ path: { owner, repo, number: prNumber } }),
    staleTime: 10_000,
  })

  const updatePullRequest = (response: NonNullable<typeof pull>) => {
    queryClient.setQueryData(repositoriesGetPullRequestQueryKey({ path: { owner, repo, number: prNumber } }), response)
    queryClient.invalidateQueries({ queryKey: repositoriesListPullRequestsQueryKey({ path: { owner, repo } }) })
  }

  const mutation = useMutation({
    ...repositoriesUpdatePullRequestMutation(),
    onSuccess: (response) => {
      updatePullRequest(response)
      queryClient.invalidateQueries({
        queryKey: repositoriesGetPullRequestEventsQueryKey({ path: { owner, repo, number: prNumber } }),
      })
      queryClient.invalidateQueries({
        queryKey: repositoriesGetPullRequestFilesOptions({
          path: { owner, repo, number: prNumber },
          query: { include_diff: false },
        }).queryKey,
      })
    },
    onError: handleError.bind(showErrorToast),
  })

  const editMutation = useMutation({
    ...repositoriesUpdatePullRequestMutation(),
    onSuccess: (response) => {
      updatePullRequest(response)
      setEditing(false)
    },
    onError: handleError.bind(showErrorToast),
  })

  if (isPending) return <RepositoryLoading label="Loading pull request" />
  if (isError || !pull) return <RepositoryError message="Unable to load pull request." retry={() => refetch()} />

  const isOpen = pull.state === "open"
  const canEdit = pull.author_username === user?.name

  return (
    <div className="space-y-6" data-testid="pull-detail">
      <RouterLink to="/$owner/$repo/pulls" params={{ owner, repo }} appearance="muted">
        <ArrowLeft className="w-4 h-4" />
        Back to pull requests
      </RouterLink>

      {editing ? (
        <div className="space-y-3">
          <Input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            data-testid="edit-pr-title"
            appearance="title"
          />
          <Textarea
            value={editBody}
            onChange={(e) => setEditBody(e.target.value)}
            rows={5}
            data-testid="edit-pr-body"
          />
          <div className="flex justify-end gap-2">
            <Button size="compact" variant="repository" onClick={() => setEditing(false)} data-testid="edit-pr-cancel">
              Cancel
            </Button>
            <Button
              size="compact"
              disabled={!editTitle.trim() || editMutation.isPending}
              onClick={() =>
                editMutation.mutate({
                  path: { owner, repo, number: prNumber },
                  body: { title: editTitle, body: editBody },
                })
              }
              data-testid="edit-pr-submit"
            >
              Save
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-4">
            <h1 className="text-xl font-semibold text-foreground sm:text-2xl">
              {pull.title} <span className="text-muted-foreground font-normal">#{pull.number}</span>
            </h1>
            <div className="flex items-center gap-2">
              {canEdit && (
                <Button
                  variant="repository"
                  size="compact"
                  onClick={() => {
                    setEditTitle(pull.title)
                    setEditBody(pull.body ?? "")
                    setEditing(true)
                  }}
                  data-testid="edit-pr"
                >
                  Edit
                </Button>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {stateBadge(pull.state)}
            <p className="text-sm text-muted-foreground">
              <strong className="font-medium text-foreground">{pull.author_username}</strong>{" "}
              {pull.state === "merged" ? "merged" : "wants to merge"}{" "}
              {commitsQuery.data ? `${commitsQuery.data.count} commits` : "changes"} from{" "}
              <code className="rounded bg-primary/10 px-1 py-0.5 text-xs text-primary">{pull.head_branch}</code> into{" "}
              <code className="rounded bg-primary/10 px-1 py-0.5 text-xs text-primary">{pull.base_branch}</code>
            </p>
          </div>
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <div>
          <TabsList appearance="pullRequest">
            <TabsTrigger value="conversation" appearance="pullRequest" aria-label="Conversation">
              <MessageSquare className="size-4" />
              Conversation{" "}
              <span className="rounded-full bg-secondary px-1.5 py-0.5 text-xs">{commentsQuery.data?.count ?? 0}</span>
            </TabsTrigger>
            <TabsTrigger value="commits" appearance="pullRequest">
              <GitCommitHorizontal className="size-4" />
              Commits{" "}
              {commitsQuery.data && (
                <span className="rounded-full bg-secondary px-1.5 py-0.5 text-xs">{commitsQuery.data.count}</span>
              )}
            </TabsTrigger>
            <TabsTrigger value="files" appearance="pullRequest" aria-label="Files Changed">
              <FileText className="size-4" />
              <span className="hidden sm:inline">Files changed</span>
              <span className="sm:hidden">Files</span>
              {changes && (
                <span className="rounded-full bg-secondary px-1.5 py-0.5 text-xs">{changes.files.length}</span>
              )}
            </TabsTrigger>
            {tab === "files" && changes && (
              <div className="ml-auto flex items-center gap-1 pr-2 text-sm" data-testid="pr-tab-diff-stats">
                <span className="text-primary">+{changes.additions}</span>
                <span className="text-destructive">-{changes.deletions}</span>
              </div>
            )}
          </TabsList>
        </div>
        <TabsContent value="conversation" appearance="pullRequest">
          {reviewsQuery.isError && (
            <RepositoryError message="Unable to load reviews." retry={() => reviewsQuery.refetch()} />
          )}
          <PullRequestConversation
            owner={owner}
            repo={repo}
            pull={pull}
            username={user?.name}
            reviews={reviewsQuery.data ?? []}
            changes={changes}
            checks={<PullRequestChecks owner={owner} repo={repo} number={prNumber} open={isOpen} />}
            mergeActions={isOpen ? <PullRequestMergeButton owner={owner} repo={repo} pull={pull} /> : null}
            closeActions={
              pull.state !== "merged" ? (
                <Button
                  variant="repository"
                  size="compact"
                  disabled={mutation.isPending}
                  onClick={() =>
                    mutation.mutate({
                      path: { owner, repo, number: prNumber },
                      body: { state: isOpen ? "closed" : "open" },
                    })
                  }
                  data-testid={isOpen ? "close-pr" : "reopen-pr"}
                >
                  {isOpen ? "Close pull request" : "Reopen"}
                </Button>
              ) : null
            }
          />
        </TabsContent>
        <TabsContent value="commits" appearance="pullRequest">
          <PullRequestCommits owner={owner} repo={repo} number={prNumber} />
        </TabsContent>
        <TabsContent value="files" appearance="pullRequest">
          {changesQuery.isPending ? (
            <RepositoryLoading label="Loading changed files" />
          ) : changesQuery.isError || !changes ? (
            <RepositoryError message="Unable to load changed files." retry={() => changesQuery.refetch()} />
          ) : (
            <PullRequestFiles
              key={`${owner}/${repo}/${prNumber}/${user?.name ?? "anonymous"}/${changes.base_commit}/${changes.head_commit}`}
              owner={owner}
              repo={repo}
              number={prNumber}
              changes={changes}
              reviews={reviewsQuery.data ?? []}
              username={user?.name}
              author={pull.author_username}
              isOpen={isOpen}
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default PullRequestDetail
