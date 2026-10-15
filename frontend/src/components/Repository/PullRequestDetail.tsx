import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useParams } from "@tanstack/react-router"
import { ArrowLeft, CircleCheck, GitMerge, GitPullRequest } from "lucide-react"
import { useState } from "react"
import {
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
  MarkdownContent,
  Link as RouterLink,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from "@/components/design-system"
import CommentsSection from "@/components/Repository/CommentsSection"
import { PullRequestFiles, ReviewTimeline } from "@/components/Repository/PullRequestFiles"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

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
      <Badge variant="secondary" data-testid="pr-state">
        <CircleCheck className="w-3 h-3" /> Closed
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
  const prNumber = Number(number)
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [editing, setEditing] = useState(false)
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
  })

  const changes = changesQuery.data
  const reviewsQuery = useQuery(reviewsListReviewsOptions({ path: { owner, repo, number: prNumber } }))

  const mutation = useMutation({
    ...repositoriesUpdatePullRequestMutation(),
    onSuccess: (response) => {
      queryClient.setQueryData(
        repositoriesGetPullRequestQueryKey({ path: { owner, repo, number: prNumber } }),
        response,
      )
      queryClient.invalidateQueries({ queryKey: repositoriesListPullRequestsQueryKey({ path: { owner, repo } }) })
      queryClient.invalidateQueries({
        queryKey: repositoriesGetPullRequestFilesOptions({
          path: { owner, repo, number: prNumber },
          query: { include_diff: false },
        }).queryKey,
      })
    },
  })

  const editMutation = useMutation({
    ...repositoriesUpdatePullRequestMutation(),
    onSuccess: (response) => {
      queryClient.setQueryData(
        repositoriesGetPullRequestQueryKey({ path: { owner, repo, number: prNumber } }),
        response,
      )
      queryClient.invalidateQueries({ queryKey: repositoriesListPullRequestsQueryKey({ path: { owner, repo } }) })
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
            <h1 className="text-xl font-bold text-foreground">
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
              {stateBadge(pull.state)}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{pull.author_username ?? "unknown"}</span>
            {pull.created_at && ` opened ${new Date(pull.created_at).toLocaleString()}`}
            {" · "}
            <span className="font-mono text-foreground">{pull.head_branch}</span> &rarr;{" "}
            <span className="font-mono text-foreground">{pull.base_branch}</span>
          </p>
        </div>
      )}

      <Tabs defaultValue="conversation">
        <div className="border-b border-border">
          <TabsList appearance="branchPicker">
            <TabsTrigger value="conversation" appearance="branchPicker">
              Conversation
            </TabsTrigger>
            <TabsTrigger value="files" appearance="branchPicker">
              Files Changed {changes && <span className="rounded bg-muted px-1.5 text-xs">{changes.files.length}</span>}
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="conversation" appearance="spaced">
          {pull.body && (
            <div className="rounded-lg border border-border bg-card px-4 py-3">
              <MarkdownContent html={pull.body_html} />
            </div>
          )}
          {reviewsQuery.isPending && <p className="text-sm text-muted-foreground">Loading reviews…</p>}
          {reviewsQuery.isError && (
            <RepositoryError message="Unable to load reviews." retry={() => reviewsQuery.refetch()} />
          )}
          <ReviewTimeline reviews={reviewsQuery.data ?? []} changes={changes} />
          <CommentsSection owner={owner} repo={repo} number={prNumber} />
        </TabsContent>
        <TabsContent value="files" appearance="spaced">
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

      <div className="flex items-center gap-2">
        {isOpen ? (
          <>
            <Button
              size="compact"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ path: { owner, repo, number: prNumber }, body: { state: "merged" } })}
              data-testid="merge-pr"
            >
              <GitMerge className="w-3.5 h-3.5" />
              Merge
            </Button>
            <Button
              variant="repository"
              size="compact"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ path: { owner, repo, number: prNumber }, body: { state: "closed" } })}
              data-testid="close-pr"
            >
              Close
            </Button>
          </>
        ) : (
          <Button
            variant="repository"
            size="compact"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate({ path: { owner, repo, number: prNumber }, body: { state: "open" } })}
            data-testid="reopen-pr"
          >
            Reopen
          </Button>
        )}
      </div>
    </div>
  )
}

export default PullRequestDetail
