import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MessageSquare } from "lucide-react"
import { type ReactNode, useState } from "react"
import {
  activityGetFeedQueryKey,
  commentsCreateCommentMutation,
  commentsDeleteCommentMutation,
  commentsListCommentsOptions,
  commentsListCommentsQueryKey,
  commentsUpdateCommentMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  ConversationCard,
  ConversationItem,
  ConversationTimeline,
  MarkdownComposer,
  MarkdownContent,
  Textarea,
} from "@/components/design-system"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface CommentsSectionProps {
  owner: string
  repo: string
  number: number
  timeline?: boolean
  author?: string
  intro?: ReactNode
  events?: ConversationEntry[]
  beforeComposer?: ReactNode
  actions?: ReactNode
}

interface ConversationEntry {
  id: string
  created_at: string
  content: ReactNode
  icon?: ReactNode
}

const CommentsSection = ({
  owner,
  repo,
  number,
  timeline = false,
  author,
  intro,
  events = [],
  beforeComposer,
  actions,
}: CommentsSectionProps) => {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { user } = useAuth()
  const [body, setBody] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editBody, setEditBody] = useState("")

  const { data, isError, isPending, refetch } = useQuery({
    ...commentsListCommentsOptions({ path: { owner, repo, number } }),
    staleTime: 10_000,
  })

  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: commentsListCommentsQueryKey({ path: { owner, repo, number } }) }),
      queryClient.invalidateQueries({ queryKey: activityGetFeedQueryKey() }),
    ])

  const mutation = useMutation({
    ...commentsCreateCommentMutation(),
    onSuccess: () => {
      setBody("")
      return invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })

  const editMutation = useMutation({
    ...commentsUpdateCommentMutation(),
    onSuccess: () => {
      setEditingId(null)
      setEditBody("")
      return invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })

  const deleteMutation = useMutation({
    ...commentsDeleteCommentMutation(),
    onSuccess: () => invalidate(),
    onError: handleError.bind(showErrorToast),
  })

  const comments = data?.data ?? []
  const entries: ConversationEntry[] = [
    ...comments.map((comment) => ({
      id: comment.id,
      created_at: comment.created_at,
      content: (
        <div data-testid={`comment-${comment.id}`}>
          <ConversationCard
            author={comment.author_username}
            date={comment.created_at}
            badge={comment.author_username === author ? "Author" : undefined}
            actions={
              comment.author_username === user?.name && editingId !== comment.id ? (
                <>
                  <Button
                    variant="text"
                    size="text"
                    onClick={() => {
                      setEditingId(comment.id)
                      setEditBody(comment.body)
                    }}
                    data-testid={`edit-comment-${comment.id}`}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="textDanger"
                    size="text"
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (window.confirm("Delete this comment?"))
                        deleteMutation.mutate({ path: { comment_id: comment.id } })
                    }}
                    data-testid={`delete-comment-${comment.id}`}
                  >
                    Delete
                  </Button>
                </>
              ) : undefined
            }
          >
            {editingId === comment.id ? (
              <div className="space-y-3">
                <Textarea
                  value={editBody}
                  onChange={(event) => setEditBody(event.target.value)}
                  data-testid={`edit-comment-input-${comment.id}`}
                />
                <div className="flex justify-end gap-2">
                  <Button
                    size="compact"
                    variant="repository"
                    onClick={() => setEditingId(null)}
                    data-testid={`edit-comment-cancel-${comment.id}`}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="compact"
                    disabled={!editBody.trim() || editMutation.isPending}
                    onClick={() => editMutation.mutate({ path: { comment_id: comment.id }, body: { body: editBody } })}
                    data-testid={`edit-comment-submit-${comment.id}`}
                  >
                    Save
                  </Button>
                </div>
              </div>
            ) : (
              <MarkdownContent html={comment.body_html} />
            )}
          </ConversationCard>
        </div>
      ),
    })),
    ...events,
  ].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
  const commentActions = (
    <>
      {actions}
      <Button
        size="compact"
        variant={timeline ? "success" : "default"}
        disabled={!body.trim() || mutation.isPending}
        onClick={() => mutation.mutate({ path: { owner, repo, number }, body: { body } })}
        data-testid="comment-submit"
      >
        {mutation.isPending ? "Commenting..." : "Comment"}
      </Button>
    </>
  )
  const composer = <MarkdownComposer value={body} onChange={setBody} testId="comment-input" actions={commentActions} />
  const content = (
    <>
      {intro}
      {isPending && (
        <p role="status" className="p-4 text-sm text-muted-foreground">
          Loading conversation…
        </p>
      )}
      {isError && (
        <p role="alert" className="p-4 text-sm">
          Unable to load comments.{" "}
          <Button variant="text" size="text" onClick={() => refetch()}>
            Retry
          </Button>
        </p>
      )}
      {entries.map((entry) =>
        timeline ? (
          <ConversationItem key={entry.id} icon={entry.icon} marker={entry.icon ? "status" : "comment"}>
            {entry.content}
          </ConversationItem>
        ) : (
          <div key={entry.id}>{entry.content}</div>
        ),
      )}
      {beforeComposer}
      {timeline ? <ConversationItem terminal>{composer}</ConversationItem> : composer}
    </>
  )
  return (
    <div className={timeline ? "min-w-0" : "space-y-4"} data-testid="comments-section">
      {!timeline && (
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <MessageSquare className="size-4" />
          {data?.count ?? 0} {data?.count === 1 ? "comment" : "comments"}
        </h2>
      )}
      {timeline ? <ConversationTimeline>{content}</ConversationTimeline> : content}
    </div>
  )
}

export default CommentsSection
