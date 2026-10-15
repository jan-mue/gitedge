import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MessageSquare } from "lucide-react"
import { useState } from "react"
import {
  activityGetFeedQueryKey,
  commentsCreateCommentMutation,
  commentsDeleteCommentMutation,
  commentsListCommentsOptions,
  commentsListCommentsQueryKey,
  commentsUpdateCommentMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, MarkdownContent, Textarea } from "@/components/design-system"
import { CommentReactions } from "@/components/Repository/CommentReactions"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface CommentsSectionProps {
  owner: string
  repo: string
  number: number
}

const CommentsSection = ({ owner, repo, number }: CommentsSectionProps) => {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { user } = useAuth()
  const [body, setBody] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editBody, setEditBody] = useState("")

  const { data } = useQuery({
    ...commentsListCommentsOptions({ path: { owner, repo, number } }),
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

  return (
    <div className="space-y-4" data-testid="comments-section">
      <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
        <MessageSquare className="w-4 h-4" />
        {data?.count ?? 0} {data?.count === 1 ? "comment" : "comments"}
      </h2>

      {comments.length > 0 && (
        <div className="space-y-3">
          {comments.map((comment) => (
            <div
              key={comment.id}
              id={`comment-${comment.id}`}
              className="border border-border rounded-lg bg-card"
              data-testid={`comment-${comment.id}`}
            >
              <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-secondary/50 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{comment.author_username}</span>
                <span>commented {new Date(comment.created_at).toLocaleString()}</span>
                {comment.author_username === user?.name && editingId !== comment.id && (
                  <div className="ml-auto flex items-center gap-2">
                    <Button
                      type="button"
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
                      type="button"
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
                  </div>
                )}
              </div>
              {editingId === comment.id ? (
                <div className="space-y-2 px-4 py-3">
                  <Textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    data-testid={`edit-comment-input-${comment.id}`}
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      size="text"
                      variant="text"
                      onClick={() => {
                        setEditingId(null)
                        setEditBody("")
                      }}
                      data-testid={`edit-comment-cancel-${comment.id}`}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="text"
                      disabled={!editBody.trim() || editMutation.isPending}
                      onClick={() =>
                        editMutation.mutate({ path: { comment_id: comment.id }, body: { body: editBody } })
                      }
                      data-testid={`edit-comment-submit-${comment.id}`}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="px-4 py-3">
                  <MarkdownContent html={comment.body_html} />
                </div>
              )}
              <CommentReactions commentId={comment.id} />
            </div>
          ))}
        </div>
      )}

      <div className="border border-border rounded-lg overflow-hidden">
        <Textarea
          id="comment-body"
          name="comment-body"
          rows={4}
          placeholder="Leave a comment"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          data-testid="comment-input"
        />
        <div className="flex items-center justify-end px-3 py-2 border-t border-border bg-secondary/50">
          <Button
            size="compact"
            disabled={!body.trim() || mutation.isPending}
            onClick={() => mutation.mutate({ path: { owner, repo, number }, body: { body } })}
            data-testid="comment-submit"
          >
            {mutation.isPending ? "Commenting..." : "Comment"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default CommentsSection
